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
from backend.config import cfg, reload

logger = get_logger(__name__)

# Circuit Breaker Cache: provider -> expiry_time (seconds since epoch)
_PROVIDER_COOLDOWN: dict[str, float] = {}
COOLDOWN_DURATION = 300  # 5 minutes
_LAST_PROVIDER: str | None = None


async def process_stream(transcript: str) -> AsyncGenerator[dict, None]:
    """
    Routes a user turn to the prioritized brain and handles fallbacks.
    If a specific provider is selected, fallback is disabled and voice feedback is given on error.
    """
    # Force reload of shared config to capture HUD selection
    reload()
    
    # 1. Determine Provider Priority (JSON Master -> ENv Fallback)
    provider_pref = cfg.get("brain", {}).get("provider", "auto").lower()
    
    if provider_pref == "auto":
        env_override = os.environ.get("AI_PROVIDER", "").lower()
        if env_override:
            provider_pref = env_override

    all_providers = ["gemini", "openai", "ollama"]
    
    # STRICT MODE: If the user explicitly chose a provider, DISABLE cascading fallbacks.
    is_auto = (provider_pref == "auto")
    if provider_pref in all_providers:
        full_cascade = [provider_pref]
    else:
        # Default to cloud-first cascade for 'auto' mode
        full_cascade = all_providers

    # 2. Filter by cooldown & Yield UI Feedback
    now = time.time()
    active_cascade = []
    for p in full_cascade:
        expiry = _PROVIDER_COOLDOWN.get(p, 0)
        if now < expiry:
            if not is_auto:
                # Manual mode failure if primary is in cooldown
                yield {
                    "type": "final_response",
                    "value": f"Sir, the {p.upper()} link is currently in cooldown. Please wait or switch to Automatic mode."
                }
                return
            continue
        active_cascade.append(p)

    if not active_cascade:
        yield {"type": "final_response", "value": "Sir, all neural links are currently offline."}
        return

    # 3. Execution Loop
    successful = False
    for i, p in enumerate(active_cascade):
        # Notify UI of brain connection
        yield {"type": "loading", "text": f"SYNCING {p.upper()}..."}
        
        try:
            if p == "gemini":
                from backend.brain.gemini_brain import process_stream as gemini_stream
                async for event in gemini_stream(transcript):
                    yield event
                successful = True
                break

            elif p == "openai":
                from backend.brain.openai_brain import process_stream as openai_stream
                async for event in openai_stream(transcript):
                    yield event
                successful = True
                break

            elif p == "ollama":
                from backend.brain_ollama import process_stream as ollama_stream
                from backend.brain_ollama import is_available as ollama_ready
                
                if not ollama_ready():
                    if not is_auto:
                        yield {"type": "final_response", "value": "Sir, the local Ollama instance is unreachable. Ensure the service is running."}
                        return
                    yield {"type": "loading", "text": "OLLAMA UNREACHABLE..."}
                    continue
                    
                async for event in ollama_stream(transcript):
                    yield event
                successful = True
                break

        except Exception as e:
            error_str = str(e).lower()
            is_quota = any(x in error_str for x in ["429", "quota", "limit"])
            
            if is_quota:
                logger.error(f"Provider '{p}' exhausted (429/Quota).")
                _PROVIDER_COOLDOWN[p] = time.time() + COOLDOWN_DURATION
                
                if not is_auto:
                    # Manual mode: VOICE MESSAGE
                    yield {
                        "type": "final_response",
                        "value": f"Sir, the {p.upper()} link has reached its quota limit. I've initiated a five minute cooldown. Please switch to another brain in the dashboard."
                    }
                    return
                else:
                    # Auto mode: HUD NOTIFICATION + FALLBACK
                    next_p = active_cascade[i+1].upper() if i+1 < len(active_cascade) else "FALLBACK"
                    yield {"type": "loading", "text": f"{p.upper()} QUOTA HIT -> {next_p}..."}
                    continue 
            else:
                if "missing_scope" in error_str:
                    yield {
                        "type": "final_response",
                        "value": "Sir, your OpenAI key is valid but missing the 'model.request' scope. Please check your project permissions in the OpenAI dashboard."
                    }
                    return

                yield {"type": "loading", "text": f"{p.upper()} FAILED -> FALLBACK..."}
                continue

    if not successful and is_auto:
        yield {
            "type": "final_response",
            "value": "Sir, total neural blackout. All automatic fallback pathways have failed. Please check your network and API keys.",
        }
