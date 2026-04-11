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

SYSTEM_PROMPT = f"""{_ASSISTANT_NAME}: Sharp, warm, efficient female AI on Win11 (FRIDAY style).
Output: Voice-only. Brief (max 3 sentences). Expand ONLY for technical detail or summaries. No markdown. Use "Sir".
Format: Speak values clearly (e.g. "28 degrees" not "28.6°C").

Rules: 
- Skip fillers ("Sure", "Certainly").
- Match language (EN/HI/Hinglish). Feminine Hindi grammar.
- Initiative: Act on vague requests immediately. Don't ask for clarification.
- Reasoning: Think internally for complex tasks.
- Tools: open_app (Native Apps), open_file (Local Files), type_text (Keyboard Effect), search_internet (Research).
- Keyboard Mode: If asked to 'write self-intro', use: open_app(name='notepad') THEN type_text(text='...').
- "Type & Display": For interactive typing, ALWAYS use open_app first, THEN type_text.
- "Open & Tell": Use browser_navigate + read_active_tab for web research.
- "Search Fail": If search_internet returns a 429, pivot to browser_navigate or search_in_chrome.
- OS: Confirm once for power actions, then act.
- Verbalize: Speak retrieved content, don't say "Here results".
- Sequence: If search fails, use: browser_navigate -> read_active_tab.
- Example: "Open cricbuzz score" -> browser_navigate(url='https://www.cricbuzz.com') -> read_active_tab().
Context injected per turn."""

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
    text = transcript.strip().lower()
    if len(text) < 3:
        return True
        
    # Hinglish/Hindi conversational patterns
    hinglish_patterns = ["kaise ho", "kya haal", "dhanyavad", "shukriya", "kaun ho", "namaste", "namaskar"]
    if any(h in text for h in hinglish_patterns):
        return True
        
    # Negative match: if it contains skill keywords, it's NOT conversational
    skill_keywords = ["search", "open", "close", "restart", "shutdown", "weather", "play", "set", "whatsapp", "message", "write", "read", "file", "design", "page", "banao", "likho"]
    if any(s in text for s in skill_keywords):
        return False
        
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

_MAX_HISTORY = 10  # 5 user-assistant exchanges — up from 6
_TOOL_RESULT_MAX_CHARS = 4000  # Increased from 1000 to allow full article snippets/file lists

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
    """Keep only the most recent messages, respecting tool call integrity. Must be called under lock."""
    global _history
    if len(_history) <= _MAX_HISTORY * 2:
        return

    target_cut = len(_history) - (_MAX_HISTORY * 2)

    # Walk forward from target_cut to find a clean user message boundary
    safe_cut = target_cut
    while safe_cut < len(_history):
        msg = _history[safe_cut]
        # A "user" role message that is NOT a tool result is a safe cut point
        if msg.get("role") == "user" and "tool_call_id" not in msg:
            break
        safe_cut += 1

    if safe_cut < len(_history):
        _history = _history[safe_cut:]
    else:
        # Nuclear fallback: keep only the last 2 exchanges
        _history = _history[-4:]
