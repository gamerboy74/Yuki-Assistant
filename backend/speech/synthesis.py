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
import time
from backend.utils.logger import get_logger
from backend.config import cfg

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'

logger = get_logger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
def _get_elevenlabs_creds():
    """Dynamically pull creds from config or env to avoid stale keys."""
    key = cfg.get("tts", {}).get("elevenlabs_api_key") or os.environ.get("ELEVENLABS_API_KEY", "")
    voice = cfg.get("tts", {}).get("elevenlabs_voice_id") or os.environ.get("ELEVENLABS_VOICE_ID", "")
    return key, voice
def _get_edge_voice():
    return os.environ.get("TTS_VOICE") or cfg["assistant"].get("tts_voice", "en-IN-NeerjaNeural")

def _get_elevenlabs_budget():
    return int(os.environ.get("ELEVENLABS_CHAR_BUDGET") or cfg.get("tts", {}).get("elevenlabs_char_budget", 2000))

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
    if _mixer_ready and pygame.mixer.music.get_busy():
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
    api_key, voice_id = _get_elevenlabs_creds()
    if not api_key or not voice_id:
        return False

    # ── Char-budget guard — avoid burning credits on long strings ──
    budget = _get_elevenlabs_budget()
    if len(text) > budget:
        logger.warning(
            f"ElevenLabs skipped: text length {len(text)} > budget {budget}. "
            "Falling back to edge-tts. Raise ELEVENLABS_CHAR_BUDGET env var to override."
        )
        return False

    try:
        import requests  # pip install requests

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
            },
        }
        headers = {
            "xi-api-key": api_key,
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

async def synthesize_to_file_async(text: str, voice_id: str | None = None, provider: str | None = None) -> str | None:
    """
    Generate audio for text and save to a temporary file, returning the path.
    Accepts optional voice_id and provider overrides (used for previews).
    """
    text = _normalize_text(text)
    tmp_path = os.path.join(tempfile.gettempdir(), f"yuki_tts_{uuid.uuid4().hex}.mp3")

    audio_ready = False
    active_provider = (provider or cfg.get("tts", {}).get("provider", "elevenlabs")).lower()

    if active_provider == "elevenlabs":
        api_key, cfg_voice_id = _get_elevenlabs_creds()
        # Use override voice_id if provided, else from config
        target_voice_id = voice_id or cfg_voice_id
        
        if api_key and target_voice_id:
            loop = asyncio.get_event_loop()
            # We need to wrap _speak_elevenlabs to use the override voice_id
            def _speak_el_custom():
                import requests
                url = f"https://api.elevenlabs.io/v1/text-to-speech/{target_voice_id}"
                payload = {
                    "text": text,
                    "model_id": "eleven_multilingual_v2",
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
                }
                headers = {"xi-api-key": api_key, "Content-Type": "application/json", "Accept": "audio/mpeg"}
                resp = requests.post(url, json=payload, headers=headers, timeout=(5, 10))
                resp.raise_for_status()
                with open(tmp_path, "wb") as f:
                    f.write(resp.content)
                return True

            try:
                audio_ready = await loop.run_in_executor(None, _speak_el_custom)
            except Exception as e:
                logger.warning(f"ElevenLabs override synthesis failed: {e}")

    if not audio_ready:
        # Fallback (or direct) to edge-tts
        try:
            import edge_tts
            target_voice = voice_id or _get_edge_voice()
            communicate = edge_tts.Communicate(text, voice=target_voice)
            await communicate.save(tmp_path)
            if os.path.getsize(tmp_path) > 0:
                audio_ready = True
        except Exception as e:
            logger.warning(f"Synthesis fallback failed: {e}")

    if audio_ready:
        return tmp_path
    return None

async def _speak_async(text: str) -> None:
    if not _ensure_mixer():
        _fallback_speak(text)
        return

    tmp_path = await synthesize_to_file_async(text)

    if not tmp_path:
        logger.error("All TTS engines failed — falling back to pyttsx3")
        _fallback_speak(text)
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


# ── Voice Listing ─────────────────────────────────────────────────────────────

async def get_voices_async():
    """Retrieve list of available Microsoft Neural and ElevenLabs voices."""
    combined_voices = []
    
    # 1. Edge-TTS Voices
    try:
        import edge_tts
        voices = await edge_tts.VoicesManager.create()
        # Find global selection
        locales = ["en-US", "en-GB", "en-IN", "hi-IN", "es-ES", "es-MX", "fr-FR", "de-DE", "ja-JP", "pt-BR", "it-IT", "ru-RU", "ko-KR", "zh-CN"]
        v_list = []
        for loc in locales:
            v_list += voices.find(Locale=loc)
        
        # Sort by locale then name
        v_list.sort(key=lambda x: (x["Locale"], x["FriendlyName"]))
        
        combined_voices.extend([
            {
                "id": v["ShortName"],
                "name": (v["FriendlyName"].split("-")[1] if "-" in v["FriendlyName"] else v["FriendlyName"]).strip(),
                "gender": v["Gender"],
                "locale": v["Locale"],
                "provider": "edge-tts",
                "isPremium": False,
                "isMultilingual": False
            }
            for v in v_list
        ])
    except Exception as e:
        logger.debug(f"edge-tts voice listing failed: {e}")

    # 2. ElevenLabs Voices (Auto-Discovery)
    try:
        api_key, _ = _get_elevenlabs_creds()
        if api_key:
            import requests # already used in _speak_elevenlabs
            url = "https://api.elevenlabs.io/v1/voices" # using v1 as it is widely supported and has simple schema
            headers = {"xi-api-key": api_key}
            
            # Offload blocking request to thread
            resp = await asyncio.to_thread(requests.get, url, headers=headers, timeout=5)
            if resp.status_code == 200:
                el_data = resp.json()
                el_list = el_data.get("voices", [])
                
                # Optimized ElevenLabs extraction
                for v in el_list:
                    labels = v.get("labels", {})
                    gender = labels.get("gender", "Female").title()
                    
                    combined_voices.append({
                        "id": v["voice_id"],
                        "name": v["name"],
                        "gender": gender,
                        "locale": "Global", 
                        "provider": "elevenlabs",
                        "isPremium": True,
                        "isMultilingual": True
                    })
    except Exception as e:
        logger.debug(f"ElevenLabs voice listing failed: {e}")

    return combined_voices

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