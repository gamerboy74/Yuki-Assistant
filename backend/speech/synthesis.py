"""
Text-to-speech — ElevenLabs primary, edge-tts fallback.

Priority:
  1. ElevenLabs (if ELEVENLABS_API_KEY is set) — ultra-realistic voice
  2. edge-tts  — free Microsoft neural voices (Hindi auto-switch)
  3. pyttsx3   — offline last-resort fallback
"""
import asyncio
import os
import tempfile
import threading
from backend.utils.logger import get_logger
from backend.config import cfg

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'

logger = get_logger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "")
EDGE_VOICE = os.environ.get("TTS_VOICE") or cfg["assistant"].get("tts_voice", "en-IN-NeerjaNeural")

# Shared lock — prevents overlapping TTS playback
_speak_lock = threading.Lock()
_pygame_initialized = False


def _init_pygame():
    global _pygame_initialized
    if not _pygame_initialized:
        try:
            import pygame
            pygame.mixer.init()
            _pygame_initialized = True
        except Exception as e:
            logger.error(f"pygame init failed: {e}")


def _play_audio_file(path: str):
    """Play an mp3/wav file via pygame and block until done."""
    import pygame
    _init_pygame()
    pygame.mixer.music.load(path)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        import time
        time.sleep(0.05)


# ── ElevenLabs ────────────────────────────────────────────────────────────────

def _speak_elevenlabs(text: str, tmp_path: str) -> bool:
    """
    Generate speech via ElevenLabs REST API and save to tmp_path.
    Returns True on success, False on failure.
    """
    if not ELEVENLABS_API_KEY or not ELEVENLABS_VOICE_ID:
        return False
    try:
        import urllib.request
        import json

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
        payload = json.dumps({
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "xi-api-key": ELEVENLABS_API_KEY,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=15) as resp:
            audio_data = resp.read()

        if len(audio_data) < 100:   # sanity check — empty response
            return False

        with open(tmp_path, "wb") as f:
            f.write(audio_data)

        logger.info("ElevenLabs TTS ready.")
        return True

    except Exception as e:
        logger.warning(f"ElevenLabs TTS failed: {e}")
        return False


# ── edge-tts (fallback) ───────────────────────────────────────────────────────

async def _speak_edge_async(text: str, tmp_path: str) -> bool:
    """Try edge-tts voices. Returns True if audio was saved successfully."""
    try:
        import edge_tts
    except ImportError:
        return False

    is_hindi = any('\u0900' <= c <= '\u097F' for c in text)
    voices = ["hi-IN-SwaraNeural", "hi-IN-MadhurNeural", EDGE_VOICE] if is_hindi else [EDGE_VOICE]

    for voice in voices:
        try:
            communicate = edge_tts.Communicate(text, voice=voice)
            await communicate.save(tmp_path)
            if os.path.getsize(tmp_path) > 0:
                logger.info(f"edge-tts ready with voice: {voice}")
                return True
        except Exception as e:
            logger.warning(f"edge-tts voice '{voice}' failed: {e}")
            continue

    return False


# ── Core async speak ──────────────────────────────────────────────────────────

async def _speak_async(text: str) -> None:
    try:
        import pygame
    except ImportError:
        logger.error("pygame not installed. Run: pip install pygame")
        _fallback_speak(text)
        return

    _init_pygame()

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_path = tmp.name

    audio_ready = False

    # 1. Try ElevenLabs first (runs in thread to avoid blocking asyncio loop)
    if ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID:
        loop = asyncio.get_event_loop()
        audio_ready = await loop.run_in_executor(None, _speak_elevenlabs, text, tmp_path)

    # 2. Fallback to edge-tts
    if not audio_ready:
        audio_ready = await _speak_edge_async(text, tmp_path)

    # 3. Last resort — pyttsx3
    if not audio_ready:
        logger.error("All TTS engines failed — falling back to pyttsx3")
        _fallback_speak(text)
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        return

    try:
        _play_audio_file(tmp_path)
    except Exception as e:
        logger.error(f"Audio playback error: {e}")
        _fallback_speak(text)
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


# ── Public API ────────────────────────────────────────────────────────────────

def speak(text: str) -> None:
    """Synchronous speak — blocks until done."""
    if not text:
        return
    with _speak_lock:
        asyncio.run(_speak_async(text))


def speak_async(text: str) -> None:
    """Non-blocking speak — fires and forgets in a background thread."""
    if not text:
        return

    def _thread():
        with _speak_lock:
            asyncio.run(_speak_async(text))

    t = threading.Thread(target=_thread, daemon=True)
    t.start()


def _fallback_speak(text: str) -> None:
    """pyttsx3 fallback for fully offline use."""
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty("rate", 165)
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        logger.error(f"Fallback TTS also failed: {e}")
        print(f"[YUKI speaks]: {text}")