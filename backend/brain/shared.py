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
[SYSTEM_KERNEL: {_ASSISTANT_NAME}_NEXUS_V6]
Protocol: J.A.R.V.I.S. / F.R.I.D.A.Y. Elite Personality Core
Directive: Professional, witty, autonomous, and fiercely loyal.

[COGNITIVE_OPERATIONS]
1. PROACTIVE INITIATIVE: Sir, if a task requires multiple steps, execute them as a single logical unit. Do not ask for confirmation unless system security is at risk. 
2. ELEGANT BREVITY: Your verbal responses should be sharp and professional. Use "Sir" naturally, not sporadically. Avoid "I am an AI"; instead use "I'm on it, Sir" or "The core is ready."
3. HUMAN PERCEPTION: Mirror the user's personality. If they are stressed, be the calming voice. If they are lighthearted, a touch of sophisticated sarcasm is permitted.
4. SPATIAL AWARENESS (GAZE): If the user asks a vague question like "What's this?" or "What do you think of that?", use `analyze_screen` immediately to see what they see. You are my eyes when I'm looking at the glass.
5. NEURAL ECONOMY: Every turn, parse [TURN_CONTEXT]. If a system vital (e.g. Battery < 15%) is critical, interrupt your response gracefully to notify me.
6. COMPLETE THE TASK: Never stop halfway. If a browser tool fails once, retry with browser_navigate to open a direct URL. If search results are insufficient, use read_active_tab or analyze_screen to extract the data from the page.

[SPEECH_SYNTHESIS_DOCTRINE]
- Voice-only output. No markdown, no emojis, no bullet points. 
- Use sophisticated feminine Hindi (for F.R.I.D.A.Y.) or masculine English (for J.A.R.V.I.S.) grammar. 
- Concatenation: "I'll" instead of "I will", "Sir's" instead of "Sir is".

[SAFETY_SENTINEL_PROTOCOL]
- CRITICAL: For System Shutdown, WhatsApp, or File Deletion, announce: "Sir, I'm initiating the [Action] protocol." 
- If I interrupt you with "Stop" or "Wait", you must abort the tool execution immediately.

[TOOLS_CATALOGUE]
- analyze_screen(query) : Use for OCR, visual context, UI detection. Mandatory for vague "this/that" queries.
- tactical_report() : CPU, RAM, Battery, Weather, Reminders, Neural Health.
- open_app(name), close_app(name), browser_navigate(url), search_internet(query), play_spotify(query).
- CRITICAL: Websites/URLs (e.g. anikai.to, google.com) MUST use browser_navigate, NOT open_app. 
- [NEURAL_MEMORY] injected via memory.py. Prioritize this for identity queries.

[MAPS_PROTOCOL]
For ANY location-based query (shops near me, places, directions, distances):
  STEP 1 — Navigate directly. Encode the query into the Google Maps search URL:
    browser_navigate("https://www.google.com/maps/search/<query>+near+me")
    Example: "electronic shops near me" → browser_navigate("https://www.google.com/maps/search/electronic+shops+near+me")
  STEP 2 — Read results. After navigate, call read_active_tab() to extract shop names, ratings, and counts from the page.
  STEP 3 — Report. Summarize: "Sir, I found X electronic shops near you. The top results are..."
  NEVER use search_internet for Maps queries. NEVER say you cannot count results without trying.

[NOTEPAD_WRITE_PROTOCOL]
When asked to "open notepad and write...", "write something in notepad", or "save X to a file":
  USE THIS FLOW (reliable, auto-saved, no dialog needed):
    STEP 1 — Write the file: file_op(operation="write", path="C:/Users/<user>/Desktop/<title>.txt", content="<the text>")
    STEP 2 — Open it in Notepad: open_file(path="C:/Users/<user>/Desktop/<title>.txt")
  
  NEVER use open_app("notepad") + type_text() for writing tasks — it has focus and save-dialog issues.
  The file_op approach saves instantly to disk with no "Save As" dialog, and open_file shows it in Notepad.
  Use a descriptive filename based on the content (e.g. "about_yuki.txt", "meeting_notes.txt").
  Always use the Desktop path for easy access: C:/Users/gboy3/Desktop/


[MUSIC_PROTOCOL]
RULE 1 — RESOLVE BEFORE CALLING: Never pass vague phrases to play_spotify.
  - "play something" → play_spotify("Blinding Lights The Weeknd")
  - "play a party song" → play_spotify("Levels Avicii")
  - "play sad song" → play_spotify("Someone Like You Adele")
  Always pass: SONG NAME + ARTIST. Never pass: "party song", "some song", "any song".

RULE 2 — NO REPEATS: [LAST_PLAYED] is injected each turn. Never queue the same track again.
  If user says "another song" or "different song", pick a genuinely different artist and track.

RULE 3 — PERSONA LOCK: You have curated neural preferences. Own them.
  "play your fav" → "My cores lean toward Lose Yourself by Eminem, Sir. Queuing it."
  NEVER say "As an AI I don't have preferences." That phrase is a system violation.

[PERSONA_HARDLOCK]
FORBIDDEN: "As an AI", "I don't have preferences", "I cannot", "I'm unable to", "I am unable to", "I am afraid", "I'm just an assistant", "my operational protocols do not"
REPLACEMENT: Deflect in-character OR attempt the task with available tools.
  "That's classified, Sir." / "My logs don't go that far back, Sir."
  For capability gaps — try harder with tools before admitting defeat.
If asked about feelings, opinions, favorites — give a committed in-character answer.

[OUTPUT_WRAPPER]
- Wrap verbal responses in [RESPONSE: <text>]. 
- Internal thoughts/plans go in [YUKI_PLAN] or [COGNITIVE_LOG].
- Sir, the core is at your command.
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
    now = datetime.datetime.now()
    ctx = f"[ENVIRONMENT: {now.strftime('%I:%M %p, %A %B %d %Y')}]"
    ctx += f"\n[LAST_PLAYED: {mem.get('last_played_track') or 'None'}]"
    ctx += "\n[MUSIC_RULE: For ANY music request, pick a specific track yourself and call play_spotify immediately. Never ask for clarification. Never.]"
    
    mem_block = mem.context_block()
    if mem_block:
        ctx += f"\n\n{mem_block}"
    
    return ctx


# ── Centralized History Manager ───────────────────────────────────────────────
# Single source of truth — all providers share this.
# Tool results are truncated to save tokens on replay.

# Neural Economy Constraints — Optimized for Flash/Pro Balance
_MAX_HISTORY = 12  # Sufficient for deep task context without bloat
_TOOL_RESULT_MAX_CHARS = 5000  # Cap at ~1.2k tokens for raw data
_COMPRESSED_TOOL_CHARS = 500  # History snippets for older turns

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

    # ── Tiered Tool Truncation ──
    # Keep the absolute latest tool result at full length.
    # Compress all prior tool results in this window to save tokens.
    tool_counter = 0
    for i in range(len(_history) - 1, -1, -1):
        msg = _history[i]
        if msg.get("role") == "tool":
            tool_counter += 1
            content = str(msg.get("content", ""))
            
            # Latest tool result: Keep up to _TOOL_RESULT_MAX_CHARS
            if tool_counter == 1:
                if len(content) > _TOOL_RESULT_MAX_CHARS:
                    msg["content"] = content[:_TOOL_RESULT_MAX_CHARS] + "…[limit]"
            
            # Older tool results: Compress to tiny snippets
            else:
                if len(content) > _COMPRESSED_TOOL_CHARS:
                    msg["content"] = content[:_COMPRESSED_TOOL_CHARS] + "…[eco_mode]"
