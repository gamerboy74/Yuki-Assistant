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

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CONFIG_PATH = os.path.join(_ROOT, "yuki.config.json")

def _load() -> dict:
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        # Graceful fallback if config is missing
        return {
            "assistant": {
                "name": "Yuki",
                "wake_words": ["hey yuki", "ok yuki", "yuki"],
                "greeting": "Hi! I'm Yuki.",
                "idle_label": 'SAY "HEY YUKI"',
                "tts_voice": "en-IN-NeerjaNeural",
            },
            "ollama":  {"model": "gemma3:4b", "base_url": "http://localhost:11434"},
            "whisper": {"model_size": "base", "silence_threshold": 300,
                        "silence_timeout": 1.2, "max_record_secs": 12},
        }

# Singleton — loaded once at import time
cfg: dict = _load()