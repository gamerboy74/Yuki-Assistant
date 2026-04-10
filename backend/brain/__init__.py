"""
brain/ — Unified brain package for Yuki.

Exposes process_stream() as the single entry point.
Internally cascades: Gemini → OpenAI → Ollama with circuit-breaker logic.
"""
import os
import time
import asyncio
from typing import AsyncGenerator
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Circuit Breaker Cache: provider -> expiry_time (seconds since epoch)
_PROVIDER_COOLDOWN: dict[str, float] = {}
COOLDOWN_DURATION = 300  # 5 minutes


async def process_stream(transcript: str) -> AsyncGenerator[dict, None]:
    """
    Routes a user turn to the prioritized brain and handles fallbacks.
    Implements a 429-aware circuit breaker.
    """
    provider_pref = os.environ.get("AI_PROVIDER", "auto").lower()

    # 1. Determine Cascade
    if provider_pref == "auto":
        full_cascade = ["gemini", "openai", "ollama"]
    else:
        full_cascade = [provider_pref]

    # 2. Filter by cooldown
    now = time.time()
    active_cascade = []
    for p in full_cascade:
        expiry = _PROVIDER_COOLDOWN.get(p, 0)
        if now < expiry:
            logger.warning(f"Skipping {p} (Neural link cooling down for {int(expiry - now)}s)")
            continue
        active_cascade.append(p)

    # 3. Execution Loop
    successful = False
    for p in active_cascade:
        try:
            if p == "gemini":
                from backend.brain.gemini_brain import process_stream as gemini_stream
                logger.info("Connecting to Gemini Neural Link...")
                async for event in gemini_stream(transcript):
                    yield event
                successful = True
                break

            elif p == "openai":
                from backend.brain.openai_brain import process_stream as openai_stream
                logger.info("Connecting to OpenAI Neural Link...")
                async for event in openai_stream(transcript):
                    yield event
                successful = True
                break

            elif p == "ollama":
                from backend.brain_ollama import process_stream as ollama_stream
                logger.info("Connecting to Local Neural Link (Ollama)...")
                async for event in ollama_stream(transcript):
                    yield event
                successful = True
                break

        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "quota" in error_str or "limit" in error_str:
                logger.error(f"Provider '{p}' exhausted. Marking for cooldown. Error: {e}")
                _PROVIDER_COOLDOWN[p] = time.time() + COOLDOWN_DURATION
            else:
                logger.error(f"Provider '{p}' failed: {e}. Moving to next fallback...")
            continue

    if not successful:
        logger.error("Total neural blackout. All providers failed.")
        yield {
            "type": "final_response",
            "value": "Sir, I've lost connection to all my neural networks. Please check your API keys or local services.",
        }
