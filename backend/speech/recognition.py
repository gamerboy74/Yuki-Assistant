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
import numpy as np

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

class AsyncWhisperStreamer:
    """
    Modern, async-friendly interface for faster-whisper.
    Uses in-memory buffers to avoid disk I/O latency.
    """
    def __init__(self):
        self.model = None
        self.model_size = get_model_size()
        self._load_model()
        
    def _load_model(self):
        """Lazy load and warm up the model on the GPU."""
        try:
            from faster_whisper import WhisperModel
            import torch
            
            device = "cuda" if torch.cuda.is_available() else "cpu"
            compute = "float16" if device == "cuda" else "int8"
            
            model_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "whisper")
            os.makedirs(model_path, exist_ok=True)
            
            logger.info(f"Loading Whisper {self.model_size} on {device.upper()}...")
            self.model = WhisperModel(
                self.model_size, 
                device=device, 
                compute_type=compute,
                download_root=model_path
            )
            logger.info("Whisper loaded.")
        except Exception as e:
            logger.error(f"Whisper initialization failed: {e}")
            raise

    def reload_model(self):
        """Force reload of the whisper model (e.g. if model size changed)."""
        import gc
        self.model = None
        gc.collect()
        self._load_model()

    async def transcribe_bytes(self, audio_data: bytes) -> str:
        """
        Transcribe a block of 16kHz mono PCM bytes in-memory.
        No WAV header required for np manipulation.
        """
        if not audio_data:
            return ""
            
        try:
            # Convert bytes to float32 np array (faster-whisper baseline)
            audio_int16 = np.frombuffer(audio_data, dtype=np.int16)
            audio_float32 = audio_int16.astype(np.float32) / 32768.0
            
            # Start transcription (runs in thread pool if not explicitly async)
            segments, info = self.model.transcribe(
                audio_float32,
                language=None, # Auto-detect English/Hindi/Hinglish
                task="transcribe",
                beam_size=5,
                vad_filter=True,
                initial_prompt=WHISPER_INITIAL_PROMPT
            )
            
            text = " ".join(seg.text for seg in segments).strip()
            if text:
                logger.info(f"STT [{info.language}]: {text!r}")
            return text
            
        except Exception as e:
            logger.error(f"In-memory transcription error: {e}")
            return ""

# Legacy compat / helper
_shared_streamer = None

def get_streamer():
    global _shared_streamer
    if _shared_streamer is None:
        _shared_streamer = AsyncWhisperStreamer()
    return _shared_streamer

def recognize_speech_sync(audio_bytes: bytes) -> str:
    """Synchronous wrapper for legacy code usage."""
    import asyncio
    streamer = get_streamer()
    return asyncio.run(streamer.transcribe_bytes(audio_bytes))

