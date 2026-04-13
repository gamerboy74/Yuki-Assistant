import io
import os
import asyncio
import numpy as np
import soundfile as sf
from typing import AsyncGenerator
from backend.utils.logger import get_logger
from backend.config import cfg

# ── Heavy Neural Imports (Lazy-loaded) ──
KPipeline = None
torch = None
torchaudio = None

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
        logger.info("KokoroEngine initialized (Neural link: Deferred).")

    async def load(self):
        """Async-friendly model loader."""
        import asyncio
        await asyncio.to_thread(self._load_engine)

    def _load_engine(self):
        global KPipeline, torch, torchaudio
        try:
            # Lazy imports
            if KPipeline is None:
                from kokoro import KPipeline as _KPipeline
                import torch as _torch
                import torchaudio as _torchaudio
                KPipeline = _KPipeline
                torch = _torch
                torchaudio = _torchaudio

            # Initialize pipeline with 'a' (American English) which handles Hinglish well.
            logger.info("Loading Kokoro-82M weights...")
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
            logger.debug("generate_audio_stream: empty text, skipping.")
            return
        # Yield a dummy to ensure this is always treated as an async generator by the runtime
        # (Python handles this correctly but being explicit prevents edge cases)

        try:
            # Kokoro generation is extremely fast on 3060.
            # It returns a generator of (graphemes, phonemes, audio)
            generator = self.pipeline(
                text, voice=voice, 
                speed=cfg["tts"].get("speed", 1.0), 
                split_pattern=r'\n+'
            )

            for _, _, audio in generator:
                if audio is not None:
                    # Convert to numpy if it's a torch Tensor
                    if hasattr(audio, 'cpu'):
                        audio = audio.cpu().numpy()
                        
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
        self.hi_voice = "hi-IN-SwaraNeural"

    async def load(self):
        """Async-friendly loader for the underlying engines."""
        await self.kokoro.load()

    def _is_hindi(self, text: str) -> bool:
        """Detect if text contains Devanagari characters."""
        return any('\u0900' <= char <= '\u097F' for char in text)

    async def speak_stream(self, text: str):
        """
        Yields audio chunks, picking the best engine for the sentence.
        """
        if self._is_hindi(text):
            logger.info(f"Using Edge-TTS for Hindi: {text[:30]}...")
            import tempfile, os
            import edge_tts
            voice = self.hi_voice  # "hi-IN-SwaraNeural"
            communicate = edge_tts.Communicate(text, voice)
            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tmp_path = tmp.name
            tmp.close()
            try:
                await communicate.save(tmp_path)
                
                # Decode MP3 to PCM using torchaudio (already in requirements)
                # to ensure consistency with Kokoro's 24kHz Mono PCM output.
                waveform, sr = torchaudio.load(tmp_path)
                
                # 1. Resample to 24000Hz (Baseline matching Kokoro)
                if sr != 24000:
                    resampler = torchaudio.transforms.Resample(sr, 24000)
                    waveform = resampler(waveform)
                
                # 2. Mix to Mono if needed
                if waveform.shape[0] > 1:
                    waveform = torch.mean(waveform, dim=0, keepdim=True)
                
                # 3. Convert to Int16 PCM
                audio_int16 = (waveform[0] * 32767).numpy().astype(np.int16).tobytes()
                yield audio_int16
                
            except Exception as e:
                logger.error(f"Edge-TTS Hindi conversion failed: {e}")
            finally:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
        else:
            logger.info(f"Using Kokoro for: {text[:30]}...")
            async for chunk in self.kokoro.generate_audio_stream(text):
                yield chunk
