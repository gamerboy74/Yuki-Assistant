"""
Wake word detection using pvporcupine (offline, instant).
Listens for "porcupine" keyword by default (free built-in keyword).
Set PICOVOICE_KEY env var for custom "yuki" keyword.
Falls back to Google STT-based detection if pvporcupine is not installed.
"""
import os
import sys
import struct
import tempfile
import threading
from backend.utils.logger import get_logger
from backend.utils.audio_filters import AudioProcessor

logger = get_logger(__name__)

PICOVOICE_KEY = os.environ.get("PICOVOICE_KEY", "")
# Built-in keywords available without a custom model file:
# alexa, americano, blueberry, bumblebee, computer, grapefruit,
# grasshopper, hey barista, hey google, hey siri, jarvis, ok google,
# picovoice, porcupine, terminator
WAKE_KEYWORD = "porcupine"  # Change to "jarvis" if you prefer

try:
    import pvporcupine
except ImportError:
    pass

try:
    import pyaudio
except ImportError:
    pass

try:
    import vosk
except ImportError:
    pass
    
class WakeWordDetector:
    """
    Offline wake word detector using pvporcupine.
    Falls back to speech_recognition Google STT if pvporcupine is unavailable.

    Thread-safety: call stop() from any thread to cancel the blocking
    listen_for_wake_word() call in another thread.
    """

    def __init__(self, wake_words=None):
        self.wake_words = wake_words or ["yuki", "hey yuki", "ok yuki"]
        self._use_porcupine = False
        self._porcupine = None
        self._pa = None
        # Audio processor for noise floor and speech detection
        self.processor = AudioProcessor()
        # Sensitivity 0.0 to 1.0 (default 0.7 for Vosk fallback)
        self.sensitivity = float(os.environ.get("WAKE_WORD_SENSITIVITY", 0.7))
        # Cancellation event — set by stop() to break listening loops
        self._stop_event = threading.Event()

        try:
            import pvporcupine
            import pyaudio

            if PICOVOICE_KEY:
                self._porcupine = pvporcupine.create(
                    access_key=PICOVOICE_KEY,
                    keywords=[WAKE_KEYWORD],
                )
            else:
                # No key — use built-in free keyword without access key check
                # pvporcupine 3.x requires access_key; fall back to STT mode
                raise ImportError("No PICOVOICE_KEY set, falling back to STT wake word")

            self._pa = pyaudio.PyAudio()
            self._use_porcupine = True
            logger.info(f"pvporcupine wake word active — listening for '{WAKE_KEYWORD}'")

        except Exception as e:
            logger.warning(f"pvporcupine not available ({e}), using STT-based wake word")
            self._use_porcupine = False

    def stop(self) -> None:
        """Signal the current listen_for_wake_word() call to return False immediately."""
        self._stop_event.set()

    def reset(self) -> None:
        """Clear the stop flag so the detector can be reused."""
        self._stop_event.clear()

    def listen_for_wake_word(self) -> bool:
        """
        Block until wake word is detected or stop() is called.
        Returns True when triggered, False on cancellation/error/interrupt.
        """
        self._stop_event.clear()
        if self._use_porcupine:
            return self._listen_porcupine()
        else:
            return self._listen_stt()

    def _listen_porcupine(self) -> bool:
        """Offline pvporcupine detection — very fast, no internet needed."""
        import pyaudio

        try:
            audio_stream = self._pa.open(
                rate=self._porcupine.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=self._porcupine.frame_length,
            )
        except OSError as e:
            logger.error(f"Cannot open audio input device for wake word: {e}")
            return False

        try:
            while not self._stop_event.is_set():
                pcm = audio_stream.read(self._porcupine.frame_length, exception_on_overflow=False)
                pcm = struct.unpack_from("h" * self._porcupine.frame_length, pcm)
                keyword_index = self._porcupine.process(pcm)
                if keyword_index >= 0:
                    logger.info(f"Wake word detected by pvporcupine (index {keyword_index})")
                    return True
            return False  # stop() was called
        except Exception as e:
            logger.error(f"Porcupine listen error: {e}")
            return False
        finally:
            audio_stream.stop_stream()
            audio_stream.close()

    def _listen_stt(self) -> bool:
        """
        Offline wake word detection using Vosk.
        Extremely fast and lightweight streaming STT.
        """
        import json

        if "vosk" not in globals() or "pyaudio" not in globals():
            logger.error("Vosk or PyAudio not installed, cannot use STT fallback")
            return False

        # Set log level to -1 to disable verbose Kaldi logging
        vosk.SetLogLevel(-1)

        # Download the model automatically if not cached
        logger.info("Loading Vosk wake word model (may download ~50MB on first run)...")
        try:
            model = vosk.Model(lang="en-us")
        except Exception as e:
            logger.error(f"Vosk failed to load model: {e}")
            return False

        logger.info(f"Vosk loading optimized grammar: {self.wake_words}")
        # Restrict Vosk to only these words + [unk] catch-all for background noise
        grammar_list = [w.lower() for w in self.wake_words]
        grammar_list.append("[unk]")
        grammar_json = json.dumps(grammar_list)

        rec = vosk.KaldiRecognizer(model, 16000, grammar_json)

        pa = pyaudio.PyAudio()
        try:
            stream = pa.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=1024, # Smaller buffer for snappier gating
            )
        except OSError as e:
            logger.error(f"Cannot open microphone for wake word: {e}")
            pa.terminate()
            return False

        logger.info("Vosk wake word detector active — say 'Hey Yuki'...")
        stream.start_stream()

        try:
            while not self._stop_event.is_set():
                try:
                    data = stream.read(512, exception_on_overflow=False)
                except Exception:
                    break

                if len(data) == 0:
                    continue

                # 1. Update background noise floor (fans, etc.)
                self.processor.update_noise_floor(data)

                # 2. Gate the audio: Only send to Vosk if it's likely speech
                if not self.processor.is_speech(data, sensitivity=self.sensitivity):
                    continue

                if rec.AcceptWaveform(data):
                    res = json.loads(rec.Result())
                    text = res.get("text", "").lower()
                else:
                    res = json.loads(rec.PartialResult())
                    text = res.get("partial", "").lower()

                if not text:
                    continue

                # Normalize common mishearings
                text = (text.replace("yuuki", "yuki")
                            .replace("you key", "yuki")
                            .replace("your key", "yuki")
                            .replace("eu key", "yuki")
                            .replace("uk", "yuki")
                            .replace("new key", "yuki"))

                for wake_word in self.wake_words:
                    if wake_word in text:
                        logger.info(f"[WAKE WORD] Vosk matched: '{wake_word}' in '{text}'")
                        return True

        except Exception as e:
            logger.error(f"Vosk streaming error: {e}")
        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()

        return False



    def delete(self):
        """Release porcupine and audio resources."""
        self.stop()
        if self._porcupine:
            self._porcupine.delete()
        if self._pa:
            self._pa.terminate()