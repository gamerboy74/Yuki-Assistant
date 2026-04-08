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

logger = get_logger(__name__)

PICOVOICE_KEY = os.environ.get("PICOVOICE_KEY", "")
# Built-in keywords available without a custom model file:
# alexa, americano, blueberry, bumblebee, computer, grapefruit,
# grasshopper, hey barista, hey google, hey siri, jarvis, ok google,
# picovoice, porcupine, terminator
WAKE_KEYWORD = "porcupine"  # Change to "jarvis" if you prefer


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
        Offline wake word detection using the project's local Whisper model.
        Much faster and more reliable than Google STT — no internet needed.
        """
        import pyaudio
        import wave
        import struct
        import numpy as np

        SAMPLE_RATE    = 16000
        CHUNK          = 1024
        RECORD_SECS    = 2.5     # listen in 2.5s windows
        ENERGY_THRESH  = 200     # RMS threshold — below this = silence, skip transcription
        FRAMES_PER_WIN = int(SAMPLE_RATE * RECORD_SECS / CHUNK)

        pa = pyaudio.PyAudio()
        try:
            stream = pa.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=SAMPLE_RATE,
                input=True,
                frames_per_buffer=CHUNK,
            )
        except OSError as e:
            logger.error(f"Cannot open microphone for wake word: {e}")
            pa.terminate()
            return False

        logger.info("Whisper wake word detector active — say 'Hey Yuki'...")

        try:
            while not self._stop_event.is_set():
                # Collect one window of audio
                frames = []
                for _ in range(FRAMES_PER_WIN):
                    if self._stop_event.is_set():
                        return False
                    try:
                        data = stream.read(CHUNK, exception_on_overflow=False)
                        frames.append(data)
                    except Exception:
                        break

                if not frames:
                    continue

                # Quick energy gate — skip silent chunks to save Whisper calls
                raw = b"".join(frames)
                samples = struct.unpack(f"{len(raw)//2}h", raw)
                rms = (sum(s * s for s in samples) / len(samples)) ** 0.5
                if rms < ENERGY_THRESH:
                    continue  # silence — don't bother transcribing

                # Save to tmp WAV and run Whisper
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    tmp_path = tmp.name

                try:
                    import wave as wav_mod
                    with wav_mod.open(tmp_path, "wb") as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)
                        wf.setframerate(SAMPLE_RATE)
                        wf.writeframes(raw)

                    from backend.speech.recognition import _get_whisper
                    model = _get_whisper()
                    segments, _ = model.transcribe(
                        tmp_path,
                        language="en",
                        beam_size=1,
                        vad_filter=True,
                    )
                    text = " ".join(s.text for s in segments).lower().strip()

                    # Normalize common mishearings
                    text = (text.replace("yuuki", "yuki")
                                .replace("you key", "yuki")
                                .replace("your key", "yuki")
                                .replace("eu key", "yuki"))

                    if text:
                        logger.debug(f"Whisper heard: {text!r}")

                    for wake_word in self.wake_words:
                        if any(w in text for w in wake_word.split()):
                            logger.info(f"Wake word matched: '{wake_word}' in '{text}'")
                            return True

                except Exception as e:
                    logger.debug(f"Whisper wake transcription error: {e}")
                finally:
                    try:
                        import os as _os
                        _os.unlink(tmp_path)
                    except Exception:
                        pass

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