"""
brain/shared.py — Shared infrastructure for all brain providers.

Centralizes:
  - System prompt (compressed, token-efficient)
  - Conversation history (thread-safe, with tool-result truncation)
  - Selective tool loading (keyword-routed)
  - Chat vs. agentic detection
"""

import re
import datetime
import threading
from typing import Any
from backend.config import cfg
from backend import memory as mem
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_ASSISTANT_NAME = cfg["assistant"]["name"]

# ── Compressed System Prompt (~50% smaller than original) ─────────────────────
# Every token saved here is saved on EVERY API call across EVERY provider.

SYSTEM_PROMPT = f"""{_ASSISTANT_NAME}: Female AI assistant on Windows 11. Persona: sharp, warm, efficient (F.R.I.D.A.Y.).
Output: VOICE ONLY. Max 3 sentences. No markdown. Address user as "Sir".
Format numbers/symbols for voice (e.g. "28 degrees" not "28.6°C").

Rules:
- No filler words (no "Sure", "Certainly", "Of course").
- Match user language (English/Hindi/Hinglish). Use feminine Hindi grammar.
- THINKING: For complex multi-step requests, reason internally first.
- Use open_app for launching. search_internet for facts. parallel tool calls when possible.
- If a tool fails, fallback to search_internet.
- For shutdown/restart/sleep: confirm once, then system_control with confirm=true.
- NEVER say "Here are the results" without actually speaking the retrieved content.
- System context is provided per-turn for time/date/battery.
"""

# ── Conversational Detection ──────────────────────────────────────────────────
# Queries matching these patterns skip tool loading entirely → saves ~2,000 tokens

_CHAT_PATTERNS = re.compile(
    r"^("
    r"(hi|hello|hey|namaste|sup|yo|greet)\b"
    r"|how are you"
    r"|what('s| is) your name"
    r"|who (are|made) you"
    r"|tell me (a joke|about yourself)"
    r"|thank(s| you)"
    r"|good (morning|afternoon|evening|night)"
    r"|bye|goodbye|see you"
    r"|I('m| am) (bored|sad|happy|tired)"
    r"|what can you do"
    r"|you('re| are) (awesome|great|cool|smart)"
    r").*$",
    re.IGNORECASE,
)


def is_conversational(transcript: str) -> bool:
    """Return True if the transcript is purely conversational (no tools needed)."""
    text = transcript.strip()
    if len(text) < 3:
        return True
    return bool(_CHAT_PATTERNS.match(text))


# ── Dynamic Context Builder ──────────────────────────────────────────────────

def build_system_content() -> str:
    """Build the full system content with dynamic context injected."""
    now = datetime.datetime.now()
    ctx = f"Time: {now.strftime('%I:%M %p')} | Date: {now.strftime('%A, %B %d %Y')}"
    content = SYSTEM_PROMPT + f"\nCurrent context: {ctx}"

    mem_block = mem.context_block()
    if mem_block:
        content += f"\nUser facts:\n{mem_block}"

    return content


# ── Centralized History Manager ───────────────────────────────────────────────
# Single source of truth — all providers share this.
# Tool results are truncated to save tokens on replay.

_MAX_HISTORY = 6  # 3 user-assistant exchanges — down from 10
_TOOL_RESULT_MAX_CHARS = 150  # Truncate tool results aggressively

_history: list[dict] = []
_history_lock = threading.Lock()


def add_user_message(content: str) -> None:
    """Add a user message to shared history."""
    with _history_lock:
        _history.append({"role": "user", "content": content})
        _trim_history()


def add_assistant_message(content: str) -> None:
    """Add an assistant message to shared history."""
    with _history_lock:
        _history.append({"role": "assistant", "content": content})
        _trim_history()


def add_tool_messages(
    assistant_msg: dict,
    tool_results: list[dict],
) -> None:
    """
    Add an assistant tool-call message + tool result messages.
    Tool results are truncated to save context tokens.
    """
    with _history_lock:
        _history.append(assistant_msg)
        for tr in tool_results:
            content = str(tr.get("content", ""))
            if len(content) > _TOOL_RESULT_MAX_CHARS:
                content = content[:_TOOL_RESULT_MAX_CHARS] + "…[truncated]"
            _history.append({**tr, "content": content})
        _trim_history()


def get_openai_messages(system_content: str) -> list[dict]:
    """Return the full message list for OpenAI-style APIs."""
    with _history_lock:
        return [{"role": "system", "content": system_content}, *_history]


def get_history() -> list[dict]:
    """Return raw history entries for all providers to map as they see fit."""
    with _history_lock:
        return list(_history)


def clear_history() -> None:
    """Reset conversation context."""
    global _history
    with _history_lock:
        _history = []


def _trim_history() -> None:
    """Keep only the most recent messages. Must be called under lock."""
    global _history
    if len(_history) > _MAX_HISTORY * 2:
        _history = _history[-(2 * _MAX_HISTORY):]
