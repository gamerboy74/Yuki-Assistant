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
from backend.speech.synthesis_kokoro import KokoroEngine

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'

logger = get_logger(__name__)

# ── Global Engines & State ───────────────────────────────────────────────────
_kokoro_engine = None
_el_circuit_broken = False  # If True, ElevenLabs is skipped for this session
_el_broken_expiry = 0       # Timestamp to retry EL
_phrase_cache = {}         # {hash: file_path} mapping for frequent phrases

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

# ── Global Stop Unification ───────────────────────────────────────────────────
_external_stop_checks = []

def add_stop_condition(check_fn):
    """Register an external boolean function to trigger audio stops."""
    if check_fn not in _external_stop_checks:
        _external_stop_checks.append(check_fn)

def _is_stopped():
    """Check if any stop signal is active."""
    if _playback_stop_event.is_set():
        return True
    for check in _external_stop_checks:
        try:
            if check(): return True
        except: pass
    return False


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

def _play_audio_file(path: str, stop_check=None):
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
        if _is_stopped():
            pygame.mixer.music.stop()
            break
        if stop_check and stop_check():
            pygame.mixer.music.stop()
            break
        time.sleep(0.01) 

    
    _last_playback_time = time.time()

async def play_audio_file_async(path: str, stop_check=None):
    """Async-friendly version of _play_audio_file."""
    if not _ensure_mixer():
        return
        
    _playback_stop_event.clear()
    
    # Pre-warm logic (replicated for async context)
    now = time.time()
    global _last_playback_time
    if (now - _last_playback_time) > 1.0:
        try:
            import numpy as np
            pre_warm_samples = int(44100 * 0.15)
            silence = np.zeros((pre_warm_samples, 2), dtype=np.int16)
            pygame.mixer.Sound(buffer=silence).play()
        except: pass

    pygame.mixer.music.load(path)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        if _is_stopped():
            pygame.mixer.music.stop()
            break
        if stop_check and stop_check():
            pygame.mixer.music.stop()
            break
        await asyncio.sleep(0.01)
    
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

    # ── 0. Phrase Cache Check ──
    import hashlib
    text_hash = hashlib.md5(text.encode()).hexdigest()
    
    # We only cache short, common system phrases to avoid bloating tempdir
    is_common = len(text) < 100
    cache_dir = os.path.join(tempfile.gettempdir(), "yuki_audio_cache")
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir, exist_ok=True)
    
    cached_path = os.path.join(cache_dir, f"{text_hash}.mp3")
    if is_common and os.path.exists(cached_path):
        # logger.debug(f"Audio cache hit for: {text[:20]}...")
        return cached_path

    audio_ready = False
    active_provider = (provider or cfg.get("tts", {}).get("provider", "elevenlabs")).lower()

    # ── 1. ElevenLabs (with Circuit Breaker) ──
    global _el_circuit_broken, _el_broken_expiry
    if active_provider == "elevenlabs":
        if _el_circuit_broken and time.time() < _el_broken_expiry:
            logger.debug("ElevenLabs circuit broken — skipping.")
        else:
            api_key, cfg_voice_id = _get_elevenlabs_creds()
            target_voice_id = voice_id or cfg_voice_id
            
            if api_key and target_voice_id:
                loop = asyncio.get_event_loop()
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
                    
                    if resp.status_code in (401, 403, 429):
                        # Break the circuit for 10 minutes if auth or rate limit error
                        global _el_circuit_broken, _el_broken_expiry
                        _el_circuit_broken = True
                        _el_broken_expiry = time.time() + 600 
                        logger.error(f"ElevenLabs fatal error {resp.status_code}. Circuit broken for 10m.")
                        return False
                    
                    resp.raise_for_status()
                    with open(tmp_path, "wb") as f:
                        f.write(resp.content)
                    return True

                try:
                    audio_ready = await loop.run_in_executor(None, _speak_el_custom)
                except Exception as e:
                    logger.warning(f"ElevenLabs synthesis failed: {e}")

    if not audio_ready and active_provider == "kokoro":
        try:
            global _kokoro_engine
            if _kokoro_engine is None:
                _kokoro_engine = KokoroEngine()
                await _kokoro_engine.load()
            
            target_voice = voice_id or "af_heart"
            # We use soundfile to save the generated PCM to a WAV/MP3 compatible format
            import soundfile as sf
            import numpy as np
            
            chunks = []
            async for chunk in _kokoro_engine.generate_audio_stream(text, voice=target_voice):
                chunks.append(np.frombuffer(chunk, dtype=np.int16))
            
            if chunks:
                full_audio = np.concatenate(chunks)
                # Kokoro outputs at 24000Hz (standard for 82M)
                # synthesis.py's mixer is at 44100Hz, but pygame handles sample rate during load.
                # To be safe, we save as a high-quality WAV.
                sf.write(tmp_path, full_audio, 24000)
                audio_ready = True
                logger.info(f"Kokoro synthesis successful with voice: {target_voice}")
        except Exception as e:
            logger.error(f"Kokoro synthesis failed: {e}")

    if not audio_ready:
        # Fallback (or direct) to edge-tts
        try:
            import edge_tts
            
            # ── Neural Cleanup: Ensure we don't pass ElevenLabs IDs to Edge-TTS ──
            # Edge-TTS voices always contain hyphens (e.g., 'en-US-GuyNeural').
            # ElevenLabs IDs are alphanumeric (e.g., 'cgSgspJ2msm6clMCkdW9').
            def is_edge_format(v: str) -> bool:
                return v and "-" in v
            
            # If the user-selected voice is NOT an Edge voice, use a safe default for fallback.
            config_voice = _get_edge_voice()
            target_voice = voice_id if is_edge_format(voice_id) else (config_voice if is_edge_format(config_voice) else "en-US-AvaMultilingualNeural")
            
            communicate = edge_tts.Communicate(text, voice=target_voice)
            await communicate.save(tmp_path)
            if os.path.getsize(tmp_path) > 0:
                audio_ready = True
                logger.info(f"Synthesis fallback successful using: {target_voice}")
        except Exception as e:
            logger.warning(f"Synthesis fallback failed: {e}")

    if audio_ready:
        # If successfully synthesized a common phrase, cache it for next time
        if is_common and not os.path.exists(cached_path):
            try:
                import shutil
                shutil.copy(tmp_path, cached_path)
            except: pass
        return tmp_path
    
    return None

async def _speak_async(text: str, stop_check=None) -> None:
    if not _ensure_mixer():
        _fallback_speak(text)
        return

    tmp_path = await synthesize_to_file_async(text)

    if not tmp_path:
        logger.error("All TTS engines failed — falling back to pyttsx3")
        _fallback_speak(text)
        return

    try:
        _play_audio_file(tmp_path, stop_check=stop_check)
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
    
    # 1. Edge-TTS Voices (Curated "Elite" Set)
    try:
        import edge_tts
        voices_manager = await edge_tts.VoicesManager.create()
        
        # We only keep the highest fidelity multilingual and local specialty voices
        # en-US-Ava and en-US-Andrew are the current gold standard for Microsoft neural.
        elite_voice_ids = [
            "en-US-AvaMultilingualNeural",
            "en-US-AndrewMultilingualNeural",
            "en-US-EmmaMultilingualNeural",
            "en-US-BrianMultilingualNeural",
            "en-GB-SoniaNeural",
            "en-GB-RyanNeural",
            "en-IN-NeerjaNeural",
            "hi-IN-SwaraNeural",
            "hi-IN-MadhurNeural",
            "ja-JP-NanamiNeural",
            "zh-CN-XiaoxiaoNeural"
        ]
        
        v_list = []
        for vid in elite_voice_ids:
            # find by ShortName
            matches = [v for v in voices_manager.voices if v["ShortName"] == vid]
            if matches:
                v = matches[0]
                v_list.append({
                    "id": v["ShortName"],
                    "name": (v["FriendlyName"].split("-")[1] if "-" in v["FriendlyName"] else v["FriendlyName"]).strip(),
                    "gender": v["Gender"],
                    "locale": v["Locale"],
                    "provider": "edge-tts",
                    "isPremium": False,
                    "isMultilingual": True if "Multilingual" in v["ShortName"] else False
                })
        
        combined_voices.extend(v_list)
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

    # 3. Kokoro Voices (Local Neural)
    try:
        # Static curated list of high-quality Kokoro-82M voices
        kokoro_voices = [
            {"id": "af_heart", "name": "Heart", "gender": "Female", "locale": "en-US", "provider": "kokoro", "isPremium": False, "isMultilingual": True},
            {"id": "af_bella", "name": "Bella", "gender": "Female", "locale": "en-US", "provider": "kokoro", "isPremium": False, "isMultilingual": True},
            {"id": "af_nicole", "name": "Nicole", "gender": "Female", "locale": "en-US", "provider": "kokoro", "isPremium": False, "isMultilingual": True},
            {"id": "af_sarah", "name": "Sarah", "gender": "Female", "locale": "en-US", "provider": "kokoro", "isPremium": False, "isMultilingual": True},
            {"id": "am_adam", "name": "Adam", "gender": "Male", "locale": "en-US", "provider": "kokoro", "isPremium": False, "isMultilingual": True},
            {"id": "am_michael", "name": "Michael", "gender": "Male", "locale": "en-US", "provider": "kokoro", "isPremium": False, "isMultilingual": True},
            {"id": "bf_emma", "name": "Emma", "gender": "Female", "locale": "en-GB", "provider": "kokoro", "isPremium": False, "isMultilingual": True},
            {"id": "bf_isabella", "name": "Isabella", "gender": "Female", "locale": "en-GB", "provider": "kokoro", "isPremium": False, "isMultilingual": True},
            {"id": "bm_george", "name": "George", "gender": "Male", "locale": "en-GB", "provider": "kokoro", "isPremium": False, "isMultilingual": True},
            {"id": "bm_lewis", "name": "Lewis", "gender": "Male", "locale": "en-GB", "provider": "kokoro", "isPremium": False, "isMultilingual": True},
        ]
        combined_voices.extend(kokoro_voices)
    except Exception as e:
        logger.debug(f"Kokoro voice listing failed: {e}")

    return combined_voices

# ── Public API ────────────────────────────────────────────────────────────────

def _run_async_safe(coro):
    """Run a coroutine safely regardless of whether a loop is already running."""
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(coro)
    finally:
        loop.close()


def speak(text: str, stop_check=None) -> None:
    """Synchronous speak — blocks until done, but bails if TTS is stuck."""
    if not text.strip():
        return
    # If another thread is stuck speaking, don't freeze the caller (main thread).
    if not _speak_lock.acquire(timeout=1.0):
        logger.warning(f"TTS lock busy, skipping speak: {text}")
        return
    try:
        _run_async_safe(_speak_async(text, stop_check=stop_check))
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