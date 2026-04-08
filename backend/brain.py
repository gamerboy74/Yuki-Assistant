"""
Yuki's Brain — Unified AI Router
==================================
Selects the AI provider based on the AI_PROVIDER environment variable.

  AI_PROVIDER=ollama   → Use local Ollama (no internet, no API key needed)
  AI_PROVIDER=openai   → Use OpenAI GPT-4o (cloud)
  AI_PROVIDER=auto     → Try Ollama first; fall back to OpenAI if unavailable

Default: auto

Model configuration:
  OLLAMA_MODEL=llama3   (default) — any model installed via `ollama pull <name>`
  OPENAI_MODEL=gpt-4o   (default)

Supports English, Hindi, Hinglish, and mixed-language responses.
"""
import os
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# ── Provider selection ────────────────────────────────────────────────────────
AI_PROVIDER  = os.environ.get("AI_PROVIDER", "auto").lower()
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")

# Lazily-resolved provider module
_provider = None


def _resolve_provider():
    """Resolve and cache the active brain provider module."""
    global _provider
    if _provider is not None:
        return _provider

    if AI_PROVIDER == "ollama":
        logger.info("AI_PROVIDER=ollama — using local Ollama brain")
        from backend import brain_ollama as provider
        _provider = provider

    elif AI_PROVIDER == "openai":
        logger.info("AI_PROVIDER=openai — using OpenAI brain")
        from backend import brain_openai as provider
        _provider = provider

    else:  # "auto" or anything else
        logger.info("AI_PROVIDER=auto — probing Ollama first...")
        from backend import brain_ollama
        if brain_ollama.is_available():
            logger.info(
                f"✅ Ollama available with model '{brain_ollama.OLLAMA_MODEL}' — "
                "using local inference"
            )
            _provider = brain_ollama
        else:
            logger.warning(
                "⚠️  Ollama not available — falling back to OpenAI GPT-4o"
            )
            from backend import brain_openai as provider
            _provider = provider

    return _provider


# ── Public API (mirrors both provider modules) ────────────────────────────────

def process(transcript: str) -> dict:
    """
    Route the transcript to the active AI provider.

    Returns a dict with keys:
        needs_clarify (bool), action (dict|None), response (str|None),
        question (str|None), options (list)
    """
    return _resolve_provider().process(transcript)


def clear_history():
    """Reset conversation context in the active provider."""
    _resolve_provider().clear_history()


def get_active_provider() -> str:
    """Return a human-readable name of the currently active AI backend."""
    prov = _resolve_provider()
    name = getattr(prov, "__name__", "") or ""
    if "ollama" in name:
        model = getattr(prov, "OLLAMA_MODEL", "llama3")
        return f"Ollama ({model})"
    return f"OpenAI ({OPENAI_MODEL})"
