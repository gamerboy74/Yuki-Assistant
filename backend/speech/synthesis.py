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
import uuid
from backend.utils.logger import get_logger
from backend.config import cfg

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'

logger = get_logger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "")
def _get_edge_voice():
    return os.environ.get("TTS_VOICE") or cfg["assistant"].get("tts_voice", "en-IN-NeerjaNeural")

# Safety: skip ElevenLabs for very long strings to avoid burning credits
ELEVENLABS_CHAR_BUDGET = int(os.environ.get("ELEVENLABS_CHAR_BUDGET", "300"))

# Shared lock — prevents overlapping TTS playback
_speak_lock = threading.Lock()
_mixer_ready = False

# Pre-import and init pygame at top-level for Windows stability.
# 44100Hz Stereo is the universal standard for digital audio.
try:
    import pygame
    if not pygame.mixer.get_init():
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=4096)
    _mixer_ready = True
except Exception as e:
    logger.error(f"pygame global init failed: {e}")
    _mixer_ready = False

_playback_stop_event = threading.Event()
_last_playback_time = 0.0  # Unix timestamp of last audio completion

def stop_speech():
    """Interrupt and stop current audio playback immediately (Barge-in)."""
    _playback_stop_event.set()
    if _pygame_initialized and pygame.mixer.music.get_busy():
        try:
            pygame.mixer.music.stop()
        except:
            pass

def _ensure_mixer():
    """Coordinate to ensure mixer is ready at 44.1kHz."""
    global _mixer_ready
    if _mixer_ready:
        return True
    
    try:
        import pygame
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=4096)
        _mixer_ready = True
        return True
    except Exception as e:
        logger.error(f"Mixer init failed in synthesis: {e}")
        return False

def _play_audio_file(path: str):
    """Play an mp3/wav file via pygame and block until done."""
    if not _ensure_mixer():
        return
        
    _playback_stop_event.clear()
    
    # ── Neural Pre-warm (150ms Silence Padding) ──
    # ONLY play if the gap since last speaking is large (> 1.0s).
    # This prevents gaps between sentences in a multi-turn response.
    now = time.time()
    global _last_playback_time
    if (now - _last_playback_time) > 1.0:
        try:
            import numpy as np
            # 44100Hz Stereo (2 channels)
            pre_warm_samples = int(44100 * 0.15)
            silence = np.zeros((pre_warm_samples, 2), dtype=np.int16)
            pygame.mixer.Sound(buffer=silence).play()
        except Exception as e:
            logger.debug(f"Pre-warm failed: {e}")

    pygame.mixer.music.load(path)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        if _playback_stop_event.is_set():
            pygame.mixer.music.stop()
            break
        time.sleep(0.01) # Tightened from 0.05 for seamless handoffs
    
    _last_playback_time = time.time()


# ── ElevenLabs ────────────────────────────────────────────────────────────────

def _speak_elevenlabs(text: str, tmp_path: str) -> bool:
    """
    Generate speech via ElevenLabs REST API and save to tmp_path.
    Returns True on success, False on failure.
    """
    if not ELEVENLABS_API_KEY or not ELEVENLABS_VOICE_ID:
        return False

    # ── Char-budget guard — avoid burning credits on long strings ──
    if len(text) > ELEVENLABS_CHAR_BUDGET:
        logger.warning(
            f"ElevenLabs skipped: text length {len(text)} > budget {ELEVENLABS_CHAR_BUDGET}. "
            "Falling back to edge-tts. Raise ELEVENLABS_CHAR_BUDGET env var to override."
        )
        return False

    try:
        import requests  # pip install requests

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
            },
        }
        headers = {
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }

        # timeout=(5, 10) means 5s connect timeout, 10s read timeout
        resp = requests.post(url, json=payload, headers=headers, timeout=(5, 10))
        resp.raise_for_status()  # surfaces HTTP 4xx/5xx with readable message
        audio_data = resp.content

        if len(audio_data) < 100:   # sanity check — empty response
            logger.warning("ElevenLabs returned suspiciously small audio payload.")
            return False

        with open(tmp_path, "wb") as f:
            f.write(audio_data)

        logger.info(f"ElevenLabs TTS ready ({len(audio_data):,} bytes).")
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
    edge_v   = _get_edge_voice()
    voices   = ["hi-IN-SwaraNeural", "hi-IN-MadhurNeural", edge_v] if is_hindi else [edge_v]

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


def _normalize_text(text: str) -> str:
    """Natural speech normalizer — converts symbols/units to spoken words."""
    import re
    # 1. Currency (e.g. $5 -> 5 dollars)
    text = re.sub(r'\$(\d+(\.\d+)?)\s*(billion|million|trillion|lakh|crore)?', r'\1 \3 dollars', text, flags=re.IGNORECASE)
    # 2. Temperature (e.g. 28.6°C -> 28.6 degree)
    text = text.replace("°C", " degree")
    text = text.replace("°", " degree")
    # 3. Speed (e.g. 13.5 km/h -> 13.5 kilometers per hour)
    text = text.replace("km/h", " kilometers per hour")
    # 4. Percent
    text = text.replace("%", " percent")
    # 5. Math/Signs
    text = text.replace("+", " plus ").replace("=", " equals ")
    # Clean up double spaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text


# ── Core async speak ──────────────────────────────────────────────────────────

async def _speak_async(text: str) -> None:
    if not _ensure_mixer():
        _fallback_speak(text)
        return

    # Expert Normalization Layer
    text = _normalize_text(text)

    # UUID name → zero collision risk when speak_async fires multiple threads
    tmp_path = os.path.join(tempfile.gettempdir(), f"yuki_tts_{uuid.uuid4().hex}.mp3")

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

def _run_async_safe(coro):
    """Run a coroutine safely regardless of whether a loop is already running."""
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(coro)
    finally:
        loop.close()


def speak(text: str) -> None:
    """Synchronous speak — blocks until done, but bails if TTS is stuck."""
    if not text.strip():
        return
    # If another thread is stuck speaking, don't freeze the caller (main thread).
    if not _speak_lock.acquire(timeout=1.0):
        logger.warning(f"TTS lock busy, skipping speak: {text}")
        return
    try:
        _run_async_safe(_speak_async(text))
    finally:
        _speak_lock.release()

def speak_async(text: str) -> None:
    """Non-blocking speak — fires and forgets in a background thread."""
    if not text:
        return

    def _thread():
        with _speak_lock:
            _run_async_safe(_speak_async(text))

    t = threading.Thread(target=_thread, daemon=True)
    t.start()


def _fallback_speak(text: str) -> None:
    """Fallback if cloud TTS fails."""
    logger.error(f"TTS failed completely. Could not speak: {text}")
    print(f"[YUKI speaks]: {text}")