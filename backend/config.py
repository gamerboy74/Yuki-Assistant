"""
Shared config loader — reads yuki.config.json from project root.
Single source of truth for both Python backend and React frontend.

Usage:
    from backend.config import cfg
    name = cfg["assistant"]["name"]       # "Yuki"
    wake = cfg["assistant"]["wake_words"] # ["hey yuki", ...]
"""
import json
import os

# Root-level configuration path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CONFIG_PATH = os.path.join(_ROOT, "yuki.config.json")

DEFAULT_CONFIG = {
    "assistant": {
        "name": "Yuki",
        "wake_words": ["hey yuki", "ok yuki", "yuki"],
        "greeting": "Hi! I'm Yuki.",
        "idle_label": 'SAY "HEY YUKI"',
        "tts_voice": "en-IN-NeerjaNeural",
        "active_timeout_sec": 8.0
    },
    "vad": {
        "speech_threshold": 0.65
    },
    "whisper": {
        "model_size": "base",
        "silence_threshold": 300,
        "silence_timeout": 1.2,
        "max_record_secs": 12
    },
    "router": {
        "enabled": True,
        "fuzzy_threshold": 0.72,
        "log_fast_path": True
    },
    "gemini": {
        "active_provider": "google_ai_studio", 
        "google_ai_studio": {
            "api_key": "",
            "model": "gemini-2.0-flash"
        },
        "fallback_model": "gemini-2.0-flash-lite",
        "use_lite_fallback": True
    },
    "openai": {
        "model": "gpt-4o-mini",
        "openai_api_key": ""
    },
    "ollama": {
        "model": "mistral:7b-instruct-q4_K_M", 
        "base_url": "http://localhost:11434"
    },
    "ai_correction": {
        "model": "mistral:7b-instruct-q4_K_M"
    },
    "tts": {
        "provider": "elevenlabs",
        "elevenlabs_char_budget": 2000,
        "elevenlabs_api_key": "",
        "elevenlabs_voice_id": "",
        "speed": 0.9
    },
    "brain": {
        "provider": "auto"
    },
    "spotify": {
        "client_id": "",
        "client_secret": ""
    },
    "audio": {
        "duck_volume": 0.15
    }
}

def _deep_update(base: dict, update: dict) -> dict:
    for k, v in update.items():
        if isinstance(v, dict) and k in base and isinstance(base[k], dict):
            _deep_update(base[k], v)
        else:
            base[k] = v
    return base

def _load() -> dict:
    config = json.loads(json.dumps(DEFAULT_CONFIG)) # Deep copy defaults
    modified = False
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            user_config = json.load(f)
            # Apply user config over defaults
            _deep_update(config, user_config)
            modified = True # Always rewrite to ensure full schema for UI
    except FileNotFoundError:
        modified = True
        
    if modified:
        try:
            with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
        except Exception:
            pass # Silently fail if can't write, will just use default RAM objects

    return config

def reload():
    """Re-load the config file from disk to capture external changes (e.g. from UI)."""
    new_data = _load()
    _deep_update(cfg, new_data)
    return cfg


# Singleton — loaded once at import time
cfg: dict = _load()

def update_from_dict(new_cfg: dict):
    """Update global config singleton and persist to disk with root-key enforcement."""
    global cfg
    
    # ── Strict Root Enforcement ──
    # Prevents "pollution" where UI-specific root keys (like 'name' or 'wakeWords') 
    # sneak into the root instead of staying inside 'assistant'.
    ALLOWED_ROOTS = {
        "assistant", "vad", "whisper", "router", "gemini", 
        "openai", "ollama", "ai_correction", "tts", "brain", "chrome", "spotify", "audio"
    }
    
    filtered_cfg = {k: v for k, v in new_cfg.items() if k in ALLOWED_ROOTS}
    
    _deep_update(cfg, filtered_cfg)
    try:
        with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass