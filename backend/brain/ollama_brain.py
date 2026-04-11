"""
Yuki's Brain — powered by local Ollama (gemma3:4b by default).
Drop-in replacement for brain.py when AI_PROVIDER=ollama in .env.

Uses Ollama's native chat REST API at http://localhost:11434/api/chat
No internet required — all inference is fully offline on the local GPU/CPU.

To pull the model:  ollama pull gemma3:4b

Improvements vs v1:
- Full JSON schema enforcement (Ollama 0.5+ structured output)
- System context injected per-turn (time, battery, OS)
- History trimmed to last 3 exchanges (prevents stale context confusion)
- Hindi / Hinglish few-shot examples in system prompt
- New actions: set_volume, reminder, get_weather, clipboard_copy
- Reduced num_predict (300) + stop tokens for faster generation
"""
import json
import os
import re
import time
import logging
import urllib.request
from typing import AsyncGenerator
import datetime
import urllib.request
import urllib.error
from typing import Any
from backend.utils.logger import get_logger
from backend.config import cfg
from backend import memory as mem

logger = get_logger(__name__)

# ── Version Detection ────────────────────────────────────────────────────────
def _get_ollama_version() -> str:
    """Attempts to get the Ollama server version."""
    try:
        url = f"{cfg['ollama']['base_url']}/api/version"
        with urllib.request.urlopen(url, timeout=2) as resp:
            return json.loads(resp.read()).get("version", "0.0.0")
    except Exception:
        return "0.0.0"

_OLLAMA_VERSION = _get_ollama_version()
_SUPPORTS_SCHEMA = _OLLAMA_VERSION >= "0.5.0"
if not _SUPPORTS_SCHEMA:
    logger.warning(f"Ollama {_OLLAMA_VERSION} < 0.5.0. Falling back to basic JSON format.")

# ── Config (JSON master with env fallback) ───────────────────────────────────
OLLAMA_BASE_URL = cfg["ollama"]["base_url"] or os.environ.get("OLLAMA_BASE_URL")
OLLAMA_MODEL    = cfg["ollama"]["model"] or os.environ.get("OLLAMA_MODEL")
_ASSISTANT_NAME = cfg["assistant"]["name"]

# ── JSON Schema (Ollama 0.5+ structured output) ───────────────────────────────
# Gemma 3 ignores "format": "json" alone and often adds prose or markdown.
# Passing the full schema enforces exact field types every time.
_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "needs_clarify": {"type": "boolean"},
        "action": {
            "type": "object",
            "properties": {
                "type":   {"type": "string"},
                "params": {"type": "object"},
            },
            "required": ["type", "params"],
        },
        "response": {"type": ["string", "null"]},
        "question": {"type": ["string", "null"]},
        "options":  {"type": "array", "items": {"type": "string"}},
    },
    "required": ["needs_clarify", "action", "response", "question", "options"],
}

SYSTEM_PROMPT = (
"""You are __ASSISTANT_NAME__, a female intelligent voice assistant on Windows 11.
Respond ONLY with a JSON object. No markdown, no explanation outside JSON.
Responses must be SHORT (1-2 sentences max — this is voice output).
You are FEMALE — always use feminine Hindi grammar (e.g. "kar sakti hoon", "bolungi", "kar diya").
If the user writes in Hindi or asks you to speak Hindi, respond in pure Hindi using DEVANAGARI SCRIPT ONLY (e.g. "हाँ, मैं हिंदी में बोल सकती हूँ।"). NEVER use romanized Hindi like "Haan main" — always use actual Unicode Devanagari characters.
For English or Hinglish queries, respond naturally in that same style.

═══ ACTIONS ═══
open_app       {"name": "app"}
close_app      {"name": "app"}
type_text      {"text": "..."}
screenshot     {}
search_web     {"query": "..."}
open_url       {"url": "https://..."}
get_weather    {"city": "city name"}
play_youtube   {"query": "...", "auto_play": true}
play_spotify   {"query": "song or artist name"}
send_whatsapp  {"contact": "name", "message": "text"}
send_whatsapp_file {"contact": "name", "file_name": "partial filename", "file_path": ""}  ← use this when user says to send a FILE/doc/ppt/pdf/image via WhatsApp
system_info    {"query": "time|date|battery|cpu|ram"}
set_volume     {"level": 0-100}
set_brightness {"level": 0-100}
file_op        {"operation": "copy|move|delete", "source": "path", "dest": "path"}
clipboard_copy {"text": "text"}
reminder       {"text": "...", "delay_minutes": 5}
none           {}

═══ JSON SCHEMA ═══
Direct:       {"needs_clarify": false, "action": {"type": "...", "params": {}}, "response": "...", "question": null, "options": []}
Clarify:      {"needs_clarify": true,  "action": {"type": "none", "params": {}}, "response": null, "question": "...", "options": ["A", "B"]}

═══ RULES ═══
1. "action" MUST be a JSON object — never null. Use {"type":"none","params":{}} for chat.
2. needs_clarify=true requires at least 2 options. NEVER hallucinate options. If the user provides a name/song, trust it and DO NOT clarify.
3. When the user says 'send file', 'send ppt', 'send document', 'share this file' over WhatsApp → ALWAYS use send_whatsapp_file, NEVER send_whatsapp.
4. WhatsApp: NEVER ask for a phone number. The native app searches by contact name only. If a name is given (e.g. 'Shiv Bhaiya'), use it directly — no clarification needed.
5. GREETINGS: For "hi", "hello", "hlo", or "namaste" — ALWAYS use action {"type":"none","params":{}}. DO NOT trigger tools for simple greetings.
6. System context {context} has real-time time/date/battery — use it.
""".replace("__ASSISTANT_NAME__", _ASSISTANT_NAME)
)

from backend.brain import shared


# ── Public API ────────────────────────────────────────────────────────────────

def is_available() -> bool:
    """Check if the Ollama server is running and the target model is available."""
    try:
        url = f"{OLLAMA_BASE_URL}/api/tags"
        with urllib.request.urlopen(url, timeout=3) as resp:
            data = json.loads(resp.read())
            model_names = [m["name"] for m in data.get("models", [])]
            return any(
                m.startswith(OLLAMA_MODEL.split(":")[0])
                for m in model_names
            )
    except Exception as e:
        logger.warning(f"Ollama availability check failed: {e}")
        return False


async def process_stream(transcript: str) -> AsyncGenerator[dict, None]:
    """
    Async generator wrapper for Gemma/Ollama.
    Simulates streaming by splitting the full response into sentences.
    """
    import asyncio
    
    # Run the synchronous 'process' in a separate thread to avoid blocking the event loop
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, process, transcript)
    
    response_text = result.get("response", "")
    action = result.get("action", {"type": "none", "params": {}})
    
    # If there is a tool action, yield it correctly
    if action and action.get("type") != "none":
        yield {"type": "tool_start", "value": action["type"]}
        # In a real streaming scenario, we'd execute the tool here, 
        # but the orchestrator handles tool execution via the 'action' dict in the final response.
        # For Ollama, we yield the end immediately since the 'process' call already finished.
        yield {"type": "tool_end", "value": action["type"]}

    if response_text:
        # Split into sentences for the TTS/HUD stream
        sentences = re.split(r'(?<=[.!?])\s+', response_text)
        for sentence in sentences:
            if sentence.strip():
                yield {"type": "text_sentence", "value": sentence.strip()}
                await asyncio.sleep(0.05) # Tiny delay for UI feel

    yield {"type": "final_response", "value": response_text or "", "action": action}


def process(transcript: str) -> dict:
    """
    Send user transcript to Ollama/Gemma 3 4B, return parsed JSON action dict.

    Returns a dict with keys:
        needs_clarify (bool), action (dict), response (str|None),
        question (str|None), options (list)
    """
    # Build system context: real-time info + persistent memory
    context   = _build_context()
    mem_block = mem.context_block()
    system_content = SYSTEM_PROMPT.replace("{context}", context).replace("{time}", datetime.datetime.now().strftime("%I:%M %p"))
    if mem_block:
        system_content = system_content + f"\n\n═══ WHAT I KNOW ABOUT THIS USER ═══\n{mem_block}"

    # Append user message to shared history
    shared.add_user_message(transcript)

    messages = [
        {"role": "system", "content": system_content},
        *shared.get_history(),
    ]

    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "format": _JSON_SCHEMA if _SUPPORTS_SCHEMA else "json",
        "options": {
            "temperature": 0.3,
            "num_predict": 300,        # Enough for our JSON, stops over-generation
            "stop": ["\n\n", "```"],   # Hard stops to prevent trailing prose
        },
    }).encode("utf-8")

    url = f"{OLLAMA_BASE_URL}/api/chat"

    try:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")

        data = json.loads(raw)
        content = data.get("message", {}).get("content", "").strip()
        logger.info(f"Gemma raw: {content[:300]}")

        # Still guard against models that ignore the schema
        content = _strip_think_tags(content)
        content = _strip_json_fences(content)

        result = json.loads(content)

        # Validate / populate required keys
        result.setdefault("needs_clarify", False)
        result.setdefault("action",       {"type": "none", "params": {}})
        result.setdefault("response",     None)
        result.setdefault("question",     None)
        result.setdefault("options",      [])

        # Ensure action is always a dict (never null — Gemma sometimes returns null)
        if not isinstance(result.get("action"), dict):
            result["action"] = {"type": "none", "params": {}}

        # Store assistant reply in shared history
        shared.add_assistant_message(content)

        return result

    except json.JSONDecodeError as e:
        logger.error(f"Gemma returned invalid JSON: {e}\nContent: {content!r}")
        return _error_response("I had trouble formatting that response. Please try again.")
    except urllib.error.URLError as e:
        logger.error(f"Ollama connection error: {e}")
        return _error_response("Local AI is not reachable. Make sure Ollama is running with: ollama serve")
    except Exception as e:
        logger.error(f"Gemma brain error: {e}")
        return _error_response(f"Something went wrong: {str(e)[:100]}")


def clear_history():
    """Reset conversation context."""
    shared.clear_history()


# ── Context injection ─────────────────────────────────────────────────────────

def _build_context() -> str:
    """Build a short system context string injected into every turn."""
    parts = []
    try:
        now = datetime.datetime.now()
        parts.append(f"Time: {now.strftime('%I:%M %p')}")
        parts.append(f"Date: {now.strftime('%A, %B %d %Y')}")
    except Exception:
        pass
    try:
        from backend.utils.monitoring import PSUTIL_AVAILABLE, psutil
        if PSUTIL_AVAILABLE:
            batt = psutil.sensors_battery()
            if batt:
                plugged = "charging" if batt.power_plugged else "on battery"
                parts.append(f"Battery: {batt.percent:.0f}% ({plugged})")
    except Exception:
        pass
    return " | ".join(parts) if parts else "Windows 11"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _strip_think_tags(text: str) -> str:
    """Remove <think>…</think> reasoning blocks that Gemma sometimes emits."""
    return re.sub(r"<think>[\s\S]*?</think>", "", text).strip()


def _strip_json_fences(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` wrappers that some models emit."""
    text = text.strip()
    pattern = r"^```(?:json)?\s*([\s\S]+?)\s*```$"
    match = re.match(pattern, text)
    if match:
        return match.group(1).strip()
    # Last-resort: grab the first {...} block
    brace_match = re.search(r"(\{[\s\S]+\})", text)
    if brace_match:
        return brace_match.group(1).strip()
    return text


def _error_response(message: str) -> dict:
    return {
        "needs_clarify": False,
        "action": {"type": "none", "params": {}},
        "response": message,
        "question": None,
        "options": [],
    }

