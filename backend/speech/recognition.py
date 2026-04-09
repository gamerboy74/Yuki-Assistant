"""
Speech recognition using faster-whisper (local, offline, multilingual).
Automatically handles English, Hindi, and Hinglish (code-switching).

Tuning env vars:
  WHISPER_MODEL_SIZE   tiny|base|small|medium  (default: base)
  SILENCE_THRESHOLD    amplitude cutoff        (default: 300)
  SILENCE_TIMEOUT      seconds of silence      (default: 1.2)
  MAX_RECORD_SECS      hard cap                (default: 12)
"""
import os
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
import wave
import struct
import tempfile
import time
import collections
import threading
from typing import Literal

from backend.utils.logger import get_logger
from backend.config import cfg

logger = get_logger(__name__)

# ── Config: env var overrides yuki.config.json which overrides built-in defaults ──
# Use properties/functions to get fresh config values
def get_model_size():
    _wc = cfg.get("whisper", {})
    return os.environ.get("WHISPER_MODEL_SIZE") or _wc.get("model_size", "base")

def get_silence_threshold():
    _wc = cfg.get("whisper", {})
    return int(os.environ.get("SILENCE_THRESHOLD") or _wc.get("silence_threshold", 300))

def get_silence_timeout():
    _wc = cfg.get("whisper", {})
    return float(os.environ.get("SILENCE_TIMEOUT") or _wc.get("silence_timeout", 1.2))

def get_max_record_secs():
    _wc = cfg.get("whisper", {})
    return int(os.environ.get("MAX_RECORD_SECS") or _wc.get("max_record_secs", 12))

# Whisper initial_prompt gives the model prior vocabulary about our app.
# This dramatically reduces mishearing of app names and the wake word.
WHISPER_INITIAL_PROMPT = (
    "Yuki, hey Yuki, open WhatsApp, open Chrome, open Spotify, open Telegram, "
    "open Discord, open VS Code, open VLC, open Notepad, open Calculator, "
    "play YouTube, search Google, screenshot, volume, battery, time, date, "
    "send message, close app."
)

_whisper_model = None
_loaded_model_size = None


def _get_whisper():
    """Lazy load Whisper model on first use or if model size changed."""
    global _whisper_model, _loaded_model_size
    
    current_size = get_model_size()

    if _whisper_model is None or _loaded_model_size != current_size:
        if _whisper_model is not None:
             logger.info(f"Model size changed from {_loaded_model_size} to {current_size}. Reloading...")
             # Clear reference to help GC
             _whisper_model = None 
             import gc
             gc.collect()

        try:
            from faster_whisper import WhisperModel

            # Auto-detect CUDA GPU — 10x faster than CPU
            try:
                import torch
                device      = "cuda"  if torch.cuda.is_available() else "cpu"
                compute     = "float16" if device == "cuda" else "int8"
            except ImportError:
                device, compute = "cpu", "int8"

            logger.info(
                f"Loading Whisper '{current_size}' on {device.upper()} "
                f"({compute}) — first run may download model..."
            )
            import faster_whisper
            model_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "whisper")
            os.makedirs(model_path, exist_ok=True)
            
            _whisper_model = faster_whisper.WhisperModel(
                current_size, device=device, compute_type=compute,
                download_root=model_path
            )
            _loaded_model_size = current_size
            logger.info(f"Whisper model loaded successfully on {device.upper()} at {model_path}.")
        except ImportError:
            logger.error("faster-whisper not installed. Run: pip install faster-whisper")
            raise
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            raise
    return _whisper_model


def recognize_speech(timeout: float = 5.0, interrupt_event: threading.Event | None = None) -> str:
    """
    Record from microphone until silence, then transcribe with Whisper.
    Returns the transcribed text (may be Hindi, English, or Hinglish).

    Improvements over original:
    - SILENCE_THRESHOLD lowered to 300 (soft voices now detected)
    - Amplitude smoothing over 500ms window (no mid-word cutoffs)
    - SILENCE_TIMEOUT lowered to 1.2s (snappier response)
    - initial_prompt injected (app names and Yuki not misheard)
    - CUDA auto-detection (GPU if available)
    """
    try:
        import pyaudio
    except ImportError:
        logger.warning("pyaudio not available, falling back to speech_recognition")
        return _fallback_recognize()

    pa = pyaudio.PyAudio()
    sample_rate = 16000
    chunk_size   = 512
    frames: list  = []
    silent_time   = 0.0
    start_time    = time.time()
    # Rolling amplitude window (~500ms) to smooth out breath pauses and retain pre-speech audio
    SMOOTH_WINDOW = 15   # 15 chunks × 32ms = ~480ms
    recent_amps: collections.deque = collections.deque(maxlen=SMOOTH_WINDOW)
    recent_data: collections.deque = collections.deque(maxlen=SMOOTH_WINDOW)

    try:
        stream = pa.open(
            rate=sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=chunk_size,
        )
    except OSError as e:
        logger.error(f"Cannot open audio input device: {e}")
        pa.terminate()
        return ""

    # ── Phase 1: wait for speech to start ────────────────────────────────────
    speech_started = False
    thold = get_silence_threshold()
    timeout_val = get_silence_timeout()

    logger.info(f"Listening... (thold={thold}, timeout={timeout_val}s)")

    while time.time() - start_time < timeout:
        if interrupt_event and interrupt_event.is_set():
            logger.info("Speech recognition interrupted (Phase 1).")
            speech_started = False
            break

        data = stream.read(chunk_size, exception_on_overflow=False)
        amplitude = max(struct.unpack_from(f"{chunk_size}h", data))
        recent_amps.append(amplitude)
        recent_data.append(data)
        avg_amp = sum(recent_amps) / len(recent_amps)
        if avg_amp > thold:
            speech_started = True
            frames.extend(recent_data)  # recover the half-second of audio before threshold was crossed
            break

    if not speech_started:
        stream.stop_stream()
        stream.close()
        pa.terminate()
        logger.info(f"No speech detected within {timeout}s (threshold={thold})")
        return ""

    # ── Phase 2: record until silence ────────────────────────────────────────
    max_record = get_max_record_secs()
    while time.time() - start_time < max_record:
        if interrupt_event and interrupt_event.is_set():
            logger.info("Speech recognition interrupted (Phase 2).")
            break

        data = stream.read(chunk_size, exception_on_overflow=False)
        frames.append(data)
        amplitude = max(struct.unpack_from(f"{chunk_size}h", data))
        recent_amps.append(amplitude)
        avg_amp = sum(recent_amps) / len(recent_amps)

        if avg_amp < thold:
            silent_time += chunk_size / sample_rate
            if silent_time >= timeout_val:
                break
        else:
            silent_time = 0.0

    stream.stop_stream()
    stream.close()
    pa.terminate()

    if not frames:
        return ""

    # ── Phase 3: transcribe with Whisper ─────────────────────────────────────
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        with wave.open(tmp_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)           # int16 = 2 bytes (constant, no PyAudio needed)
            wf.setframerate(sample_rate)
            wf.writeframes(b"".join(frames))

        whisper = _get_whisper()
        segments, info = whisper.transcribe(
            tmp_path,
            language=None,           # Auto-detect English / Hindi / Hinglish
            task="transcribe",
            beam_size=5,
            vad_filter=True,         # Re-enabled: filters silence/noise frames in audio before decoding
            vad_parameters={"min_silence_duration_ms": 300},
            initial_prompt=WHISPER_INITIAL_PROMPT,  # Vocabulary hint → fewer mishears
        )
        text = " ".join(seg.text for seg in segments).strip()
        logger.info(f"Whisper [{info.language}]: {text!r}")
        return text

    except Exception as e:
        logger.error(f"Whisper transcription error: {e}")
        return ""
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def _fallback_recognize() -> str:
    """Google STT fallback when pyaudio/whisper is unavailable."""
    try:
        import speech_recognition as sr
        recognizer = sr.Recognizer()
        with sr.Microphone() as mic:
            recognizer.adjust_for_ambient_noise(mic, duration=0.3)
            audio = recognizer.listen(mic, timeout=5)
            return recognizer.recognize_google(audio).lower()
    except Exception as e:
        logger.error(f"Fallback STT error: {e}")
        return ""

