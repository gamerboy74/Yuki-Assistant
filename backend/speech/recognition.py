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
import wave
import struct
import tempfile
import time
import collections
from typing import Literal

from backend.utils.logger import get_logger
from backend.config import cfg

logger = get_logger(__name__)

# ── Config: env var overrides yuki.config.json which overrides built-in defaults ──
_wc = cfg.get("whisper", {})

WHISPER_MODEL_SIZE: Literal["tiny", "base", "small", "medium", "large"] = (
    os.environ.get("WHISPER_MODEL_SIZE") or _wc.get("model_size", "base")   # type: ignore[assignment]
)
# int16 range is -32768..+32767.  A whisper at 30cm ≈ 200–500.
SILENCE_THRESHOLD = int(os.environ.get("SILENCE_THRESHOLD") or _wc.get("silence_threshold", 300))
# Time of silence before we stop recording (1.2s feels snappy for commands)
SILENCE_TIMEOUT   = float(os.environ.get("SILENCE_TIMEOUT") or _wc.get("silence_timeout", 1.2))
MAX_RECORD_SECS   = int(os.environ.get("MAX_RECORD_SECS")   or _wc.get("max_record_secs", 12))

# Whisper initial_prompt gives the model prior vocabulary about our app.
# This dramatically reduces mishearing of app names and the wake word.
WHISPER_INITIAL_PROMPT = (
    "Yuki, hey Yuki, open WhatsApp, open Chrome, open Spotify, open Telegram, "
    "open Discord, open VS Code, open VLC, open Notepad, open Calculator, "
    "play YouTube, search Google, screenshot, volume, battery, time, date, "
    "send message, close app."
)

_whisper_model = None


def _get_whisper():
    global _whisper_model
    if _whisper_model is None:
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
                f"Loading Whisper '{WHISPER_MODEL_SIZE}' on {device.upper()} "
                f"({compute}) — first run may download model..."
            )
            _whisper_model = WhisperModel(
                WHISPER_MODEL_SIZE, device=device, compute_type=compute
            )
            logger.info(f"Whisper model loaded on {device.upper()}.")
        except ImportError:
            logger.error("faster-whisper not installed. Run: pip install faster-whisper")
            raise
    return _whisper_model


def recognize_speech(timeout: float = 5.0) -> str:
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

    # Rolling amplitude window (~500ms) to smooth out breath pauses
    SMOOTH_WINDOW = 15   # 15 chunks × 32ms = ~480ms
    recent_amps: collections.deque = collections.deque(maxlen=SMOOTH_WINDOW)

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

    logger.info(f"Listening... (threshold={SILENCE_THRESHOLD}, timeout={SILENCE_TIMEOUT}s)")

    # ── Phase 1: wait for speech to start ────────────────────────────────────
    speech_started = False
    while time.time() - start_time < timeout:
        data = stream.read(chunk_size, exception_on_overflow=False)
        amplitude = max(struct.unpack_from(f"{chunk_size}h", data))
        recent_amps.append(amplitude)
        avg_amp = sum(recent_amps) / len(recent_amps)
        if avg_amp > SILENCE_THRESHOLD:
            speech_started = True
            frames.append(data)
            break

    if not speech_started:
        stream.stop_stream()
        stream.close()
        pa.terminate()
        logger.info(f"No speech detected within {timeout}s (threshold={SILENCE_THRESHOLD})")
        return ""

    # ── Phase 2: record until silence ────────────────────────────────────────
    while time.time() - start_time < MAX_RECORD_SECS:
        data = stream.read(chunk_size, exception_on_overflow=False)
        frames.append(data)
        amplitude = max(struct.unpack_from(f"{chunk_size}h", data))
        recent_amps.append(amplitude)
        avg_amp = sum(recent_amps) / len(recent_amps)

        if avg_amp < SILENCE_THRESHOLD:
            silent_time += chunk_size / sample_rate
            if silent_time >= SILENCE_TIMEOUT:
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
            vad_filter=True,         # Strip silence before processing
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

