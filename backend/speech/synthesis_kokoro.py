import io
import os
import asyncio
import numpy as np
import soundfile as sf
from typing import AsyncGenerator
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Kokoro language codes: 'a' for American English, 'b' for British, 'j' for Japanese, 'z' for Chinese
# For Hinglish, 'a' (American) usually sounds the most like the premium ElevenLabs voices.
DEFAULT_VOICE = "af_heart" # A high-quality feminine voice

class KokoroEngine:
    """
    Local high-performance TTS engine using Kokoro-82M.
    Requires espeak-ng installed on the system.
    """
    def __init__(self):
        self.pipeline = None
        self._load_engine()

    def _load_engine(self):
        try:
            from kokoro import KPipeline
            import torch
            
            # Initialize pipeline with 'a' (American English) which handles Hinglish well.
            self.pipeline = KPipeline(lang_code='a') 
            logger.info("Kokoro-82M engine loaded.")
        except Exception as e:
            logger.error(f"Failed to load Kokoro: {e}")
            raise

    async def generate_audio_stream(self, text: str, voice: str = DEFAULT_VOICE) -> AsyncGenerator[bytes, None]:
        """
        Generate audio chunks for the given text.
        Yields raw PCM bytes (16kHz, mono).
        """
        if not text.strip():
            return

        try:
            # Kokoro generation is extremely fast on 3060.
            # It returns a generator of (graphemes, phonemes, audio)
            generator = self.pipeline(
                text, voice=voice, 
                speed=1.1, split_pattern=r'\n+'
            )

            for _, _, audio in generator:
                if audio is not None:
                    # Convert float32 [-1, 1] to int16 PCM
                    audio_int16 = (audio * 32767).astype(np.int16).tobytes()
                    yield audio_int16
                    
        except Exception as e:
            logger.error(f"Kokoro generation error: {e}")

class HPVoiceSwitcher:
    """
    Smart switcher between Kokoro (Local HP) and Edge-TTS (High fidelity Hindi).
    """
    def __init__(self):
        self.kokoro = KokoroEngine()
        import edge_tts
        self.hi_voice = "hi-IN-SwaraNeural"

    def _is_hindi(self, text: str) -> bool:
        """Detect if text contains Devanagari characters."""
        return any('\u0900' <= char <= '\u097F' for char in text)

    async def speak_stream(self, text: str):
        """
        Yields audio chunks, picking the best engine for the sentence.
        """
        if self._is_hindi(text):
            logger.info(f"Using Edge-TTS for Hindi: {text[:30]}...")
            # Fallback to current edge-tts logic (which is already good for Hindi)
            # We'll wrap this in the orchestrator later
            pass
        else:
            logger.info(f"Using Kokoro for: {text[:30]}...")
            async for chunk in self.kokoro.generate_audio_stream(text):
                yield chunk
