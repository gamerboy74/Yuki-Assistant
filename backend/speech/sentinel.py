import torch
import numpy as np
import threading
import time
import os
from typing import Generator
from backend.utils.logger import get_logger

logger = get_logger(__name__)

class VoiceSentinel:
    """
    High-performance VAD using Silero.
    Optimized for low-latency barge-in and precise speech detection.
    Running on RTX 3060 (OpenMP/CUDA) via torch.
    """
    
    def __init__(self, sample_rate: int = 16000, threshold: float = 0.65):
        self.sample_rate = sample_rate
        env_threshold = os.environ.get("VAD_SPEECH_THRESHOLD")
        
        from backend.config import cfg
        cfg_threshold = cfg.get("vad", {}).get("speech_threshold", threshold)
        
        if env_threshold is not None:
            try:
                cfg_threshold = float(env_threshold)
            except ValueError:
                logger.warning(f"Invalid VAD_SPEECH_THRESHOLD='{env_threshold}', using default {cfg_threshold}")
                
        # Clamp for safety: too low catches TV/background, too high misses user speech.
        self.threshold = min(max(cfg_threshold, 0.1), 0.95)
        self.model = None
        self.utils = None
        
        # Buffer for VAD (Silero expects 512, 1024, or 1536 samples)
        self.chunk_size = 512
        logger.info(f"VoiceSentinel initialized (awaiting neural link). Threshold: {self.threshold:.2f}")

    async def load(self):
        """Async-friendly model loader."""
        import asyncio
        await asyncio.to_thread(self._load_model)
        
    def _load_model(self):
        """Load Silero VAD model from torch hub."""
        logger.info("Loading Silero VAD model...")
        try:
            # Force local cache usage if possible, otherwise download
            self.model, self.utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                trust_repo=True
            )
            # Use GPU if available
            if torch.cuda.is_available():
                self.model = self.model.cuda()
                logger.info("Silero VAD running on CUDA")
            else:
                logger.info("Silero VAD running on CPU")
                
        except Exception as e:
            logger.error(f"Failed to load Silero VAD: {e}")
            raise

    def is_speech(self, pcm_data: bytes) -> bool:
        """
        Check if a single chunk contains speech.
        Expects 16-bit PCM mono 16kHz audio.
        """
        if not pcm_data or self.model is None:
            return False
            
        # Convert bytes to float32 tensor
        audio_int16 = np.frombuffer(pcm_data, dtype=np.int16)
        audio_float32 = audio_int16.astype(np.float32) / 32768.0
        
        # Silero expects (batch_size, samples)
        with torch.no_grad():
            tensor = torch.from_numpy(audio_float32)
            if torch.cuda.is_available():
                tensor = tensor.cuda()
            
            # Get confidence score
            confidence = self.model(tensor, self.sample_rate).item()
            
        return confidence > self.threshold

    def get_speech_confidence(self, pcm_data: bytes) -> float:
        """Return raw confidence score (0.0 to 1.0)"""
        if not pcm_data or self.model is None:
            return 0.0
            
        audio_int16 = np.frombuffer(pcm_data, dtype=np.int16)
        audio_float32 = audio_int16.astype(np.float32) / 32768.0
        
        with torch.no_grad():
            tensor = torch.from_numpy(audio_float32)
            if torch.cuda.is_available():
                tensor = tensor.cuda()
            return self.model(tensor, self.sample_rate).item()

class VADStreamProcessor:
    """
    Wraps VoiceSentinel to handle a stream of audio bytes and yield 
    aggregated 'SpeechStarted' and 'SpeechEnded' events.
    """
    def __init__(self, sentinel: VoiceSentinel):
        self.sentinel = sentinel
        self.is_speaking = False
        self.silence_chunks = 0
        self.speech_chunks = 0
        
        # Tunable parameters for smoother detection
        self.min_speech_trigger = 2   # ~64ms of speech to trigger
        self.min_silence_trigger = 25 # ~800ms of silence to end
        
    def process_chunk(self, chunk: bytes) -> str | None:
        """
        Process a chunk and return an event string if state changed.
        'speech_start', 'speech_end', or None.
        """
        speech_detected = self.sentinel.is_speech(chunk)
        
        if speech_detected:
            self.silence_chunks = 0
            self.speech_chunks += 1
            if not self.is_speaking and self.speech_chunks >= self.min_speech_trigger:
                self.is_speaking = True
                return "speech_start"
        else:
            self.speech_chunks = 0
            self.silence_chunks += 1
            if self.is_speaking and self.silence_chunks >= self.min_silence_trigger:
                self.is_speaking = False
                return "speech_end"
                
        return None
