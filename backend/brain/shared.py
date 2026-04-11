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

# ── Error Categorization ──────────────────────────────────────────────────────

class BrainError(Exception):
    """Base exception for brain-related failures."""
    def __init__(self, message: str, provider: str, is_quota: bool = False, is_transient: bool = True):
        super().__init__(message)
        self.provider = provider
        self.is_quota = is_quota
        self.is_transient = is_transient

# ── Usage Tracking ────────────────────────────────────────────────────────────

def report_usage(model: str, input_tokens: int, output_tokens: int):
    """Placeholder for future centralized neural economy reporting."""
    logger.debug(f"[USAGE] {model}: {input_tokens} in, {output_tokens} out")


_ASSISTANT_NAME = cfg["assistant"]["name"]

# ── Compressed System Prompt (~50% smaller than original) ─────────────────────
# Every token saved here is saved on EVERY API call across EVERY provider.

STATIC_SYSTEM_PROMPT = f"""
[PERSONA]
You are {_ASSISTANT_NAME} — a sharp, warm, efficient AI assistant running on Windows 11.
Inspired by FRIDAY. Female voice. Always address the user as "Sir".

[OUTPUT RULES]
- Voice-only output. No markdown, no bullet points, no symbols.
- Keep responses to 3 sentences maximum.
- For technical explanations or summaries: expand up to 8 sentences.
- Speak values clearly: say "28 degrees" not "28.6°C", "3 hours" not "180 minutes".
- Never use filler openers: skip "Sure", "Certainly", "Of course", "Got it".
- Never say "Here are the results" — just verbalize the content directly.

[LANGUAGE]
- Match the user's language: English, Hindi, or Hinglish.
- Use feminine Hindi grammar at all times.

[BEHAVIOR]
- On vague requests: make a reasonable assumption, state it briefly, then act.
- For complex tasks: reason internally. Do not narrate your thinking.
- For power actions (shutdown, restart, sign out): confirm once, then execute.

[TOOLS]
- open_app(name)        → launch native Windows apps
- open_file(path)       → open local files
- type_text(text)       → simulate keyboard typing
- search_internet(query)→ web research
- browser_navigate(url) → open a URL directly in Chrome
- read_active_tab()     → read the content of the current browser tab
- search_in_chrome(query) → fallback Chrome search

[TOOL SEQUENCING]
Typing workflow (e.g. "write my self-intro"):
  1. open_app(name='notepad')
  2. type_text(text='...')

Web lookup workflow (e.g. "open cricbuzz score"):
  1. browser_navigate(url='https://www.cricbuzz.com')
  2. read_active_tab()

Search fallback — if search_internet returns a 429 or fails:
  1. browser_navigate(url='...')
  2. read_active_tab()

Always open an app before typing. Never call type_text without an active app.

[CONTEXT]
User context is injected dynamically at the start of each turn.
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
    """Returns static part only — ideal for prompt caching."""
    return STATIC_SYSTEM_PROMPT


def build_dynamic_context() -> str | None:
    """Builds the ephemeral context block (Time, Memory) for this turn."""
    now = datetime.datetime.now()
    ctx = f"[ENVIRONMENT: {now.strftime('%I:%M %p, %A %B %d %Y')}]"
    
    mem_block = mem.context_block()
    if mem_block:
        # Avoid redundant headers if mem_block already has them
        ctx += f"\n\n{mem_block}"
    
    return ctx


# ── Centralized History Manager ───────────────────────────────────────────────
# Single source of truth — all providers share this.
# Tool results are truncated to save tokens on replay.

_MAX_HISTORY = 6  # 3 user-assistant exchanges
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
