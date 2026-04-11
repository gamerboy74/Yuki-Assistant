"""
STT Post-Correction using local Gemma (via Ollama).
Fixes common Whisper mishears for voice-command contexts.

This module is intentionally lightweight — it only fixes
clear misrecognitions. It does NOT alter punctuation or
restructure the sentence. Falls back to the original text
on any error.

Previously used GPT-3.5-turbo (online). Now fully offline.
"""
import json
import os
import urllib.request
from backend.utils.logger import get_logger
from backend.config import cfg

logger = get_logger(__name__)

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL") or cfg.get("ollama", {}).get("base_url", "http://localhost:11434")
OLLAMA_MODEL    = os.environ.get("OLLAMA_MODEL") or cfg.get("ai_correction", {}).get("model", "gemma3:4b")

_CORRECTION_PROMPT = """\
You are a speech recognition post-processor for a Windows voice assistant called Yuki.
Fix ONLY clear misrecognitions. Do not paraphrase. Do not change the meaning. Do not add words.
Return ONLY the corrected text — no explanation, no quotes, no punctuation changes.

Common mishears to fix:
- "lucky" / "wiki" / "yugi" / "yucky" → "Yuki"
- "what's up" / "watts up" → "WhatsApp" (when it's an app context)
- "v.l.c." / "vielsy" → "VLC"
- "vs coat" / "vs cord" → "VS Code"
- "note pet" / "note path" → "Notepad"
- "tel agram" → "Telegram"
- "you tube" → "YouTube"

Examples:
Input:  open lucky
Output: open Yuki

Input:  open what's up
Output: open WhatsApp

Input:  search for delhi weather
Output: search for delhi weather

Now fix this input:\
"""


# Known Whisper mishear patterns for Yuki-specific vocabulary.
# correct_transcript() is only called when one of these is found.
# This avoids the ~1-2s Ollama round-trip for clean speech.
_MISHEAR_PATTERNS = (
    "lucky", "wiki", "yugi", "yucky", "wikki",     # "Yuki" mishears
    "what's up", "watts up", "whatsap",             # "WhatsApp" mishears
    "v.l.c", "vielsy", "vlsy",                      # VLC
    "vs coat", "vs cord", "vs code", "vscode",      # VS Code (vscode is correct, others aren't)
    "note pet", "note path", "noteped",             # Notepad
    "tel agram", "telegram",                        # Telegram (telegram itself is fine)
    "you tube",                                     # YouTube (two words)
)


def _should_correct(text: str) -> bool:
    """Return True only if a known mishear pattern is present in the text."""
    lower = text.lower()
    return any(p in lower for p in _MISHEAR_PATTERNS)


def correct_transcript(text: str) -> str:
    """
    Attempt to fix STT mishears using local Gemma.
    Returns the corrected text, or the original text if correction fails.
    Falls back silently — never crashes the main pipeline.

    Only calls Gemma when a known mishear pattern is detected, to avoid
    adding latency to clean speech.
    """
    if not text or len(text) < 3:
        return text

    if not _should_correct(text):
        return text   # No known mishear patterns — skip the Ollama round-trip



    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": f"{_CORRECTION_PROMPT}\nInput: {text}\nOutput:",
        "stream": False,
        "options": {
            "temperature": 0.1,   # Very low — deterministic correction
            "num_predict": 60,
        },
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            f"{OLLAMA_BASE_URL}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
        corrected = data.get("response", "").strip()
        if corrected and corrected != text:
            logger.info(f"STT correction: {text!r} -> {corrected!r}")
            return corrected
        return text
    except Exception as e:
        logger.debug(f"STT correction skipped ({e})")
        return text