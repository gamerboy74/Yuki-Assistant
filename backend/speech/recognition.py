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
import asyncio
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
# Including common Hinglish and Hindi commands significantly improves recognition of mixed speech.
WHISPER_INITIAL_PROMPT = (
    "Yuki, hey Yuki, mera naam, what is my name, gaana bajao, music play, open Spotify, "
    "kholo, band karo, batao, suno, samajh gaye, weather update, search Google, "
    "screenshot, volume, battery, time, WhatsApp, YouTube chalao."
)


class AsyncWhisperStreamer:
    """
    Modern, async-friendly interface for faster-whisper.
    Uses in-memory buffers to avoid disk I/O latency.
    """
    def __init__(self, local_files_only: bool = True):
        self.model = None
        self.model_size = get_model_size()
        self.local_files_only = local_files_only
        # Pull dynamic language mode from config
        self.lang_mode = cfg.get("assistant", {}).get("language_mode", "auto").lower()
        logger.info(f"AsyncWhisperStreamer initialized. Mode: {'Offline' if local_files_only else 'Online'}, Language: {self.lang_mode}")
        
    def _load_model(self):
        """Lazy load and warm up the model on the GPU."""
        try:
            from faster_whisper import WhisperModel
            import torch
            
            device = "cuda" if torch.cuda.is_available() else "cpu"
            # Hard-lock float16 for CUDA to maximize tensor core usage
            compute = "float16" if device == "cuda" else "int8"
            
            model_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "whisper")
            os.makedirs(model_path, exist_ok=True)
            
            logger.info(f"Loading Whisper {self.model_size} on {device.upper()} (Compute: {compute}, LocalOnly: {self.local_files_only})...")
            self.model = WhisperModel(
                self.model_size, 
                device=device, 
                compute_type=compute,
                download_root=model_path,
                local_files_only=self.local_files_only
            )
            logger.info("Whisper weights linked to GPU.")
        except Exception as e:
            if self.local_files_only:
                logger.warning(f"Whisper offline load failed (missing weights?). Retrying with online check: {e}")
                self.local_files_only = False
                return self._load_model()
            logger.error(f"Whisper initialization failed: {e}")
            raise

    def unload(self):
        """Release model from VRAM. Next transcribe_bytes call will reload."""
        if self.model is not None:
            del self.model
            self.model = None
            import gc
            import torch
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            logger.info("Whisper model unloaded from VRAM.")

    def is_loaded(self) -> bool:
        return self.model is not None

    async def load(self):
        """Async-friendly model loader."""
        import asyncio
        await asyncio.to_thread(self._load_model)

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
            # Refresh language mode from config in case it changed in the UI
            self.lang_mode = cfg.get("assistant", {}).get("language_mode", "auto").lower()
            
            # Map simplified names to Whisper ISO codes
            whisper_lang = None # Default Auto
            if self.lang_mode == "hindi" or self.lang_mode == "hinglish":
                whisper_lang = "hi"
            elif self.lang_mode == "english":
                whisper_lang = "en"

            # Convert bytes to float32 np array (faster-whisper baseline)
            audio_int16 = np.frombuffer(audio_data, dtype=np.int16)
            audio_float32 = audio_int16.astype(np.float32) / 32768.0
            
            # ── Optimization: Offload blocking transcription to thread pool ──
            # This prevents the Python event loop from freezing during GPU compute.
            def _run():
                segments, info = self.model.transcribe(
                    audio_float32,
                    language=whisper_lang,  # Locked if configured
                    task="transcribe",
                    beam_size=1,            # Neural Economy: 1 is much faster for real-time interaction
                    vad_filter=True,
                    initial_prompt=WHISPER_INITIAL_PROMPT
                )
                text = " ".join(seg.text for seg in segments).strip()
                return text, info

            text, info = await asyncio.to_thread(_run)
            
            if text:
                logger.info(f"STT [{info.language}]: {text!r}")
            return text
            
        except Exception as e:
            logger.error(f"In-memory transcription error: {e}")
            return ""

    async def warm_up(self):
        """Pre-warm the GPU by running a tiny slice of silence."""
        logger.info("Warming up Whisper neural engine...")
        silence = np.zeros(16000, dtype=np.float32)
        await asyncio.to_thread(self.model.transcribe, silence)
        logger.info("Whisper engine primed.")

# Legacy compat / helper
_shared_streamer = None

def get_streamer():
    global _shared_streamer
    if _shared_streamer is None:
        _shared_streamer = AsyncWhisperStreamer()
    return _shared_streamer


