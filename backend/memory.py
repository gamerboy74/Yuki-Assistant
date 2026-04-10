"""
memory.py — Persistent memory store for Yuki.

Two-layer memory:
  1. Long-term:  JSON file on disk (survives restarts). Stores user profile +
                 facts the user explicitly asked Yuki to remember.
  2. Short-term: In-process ring of the last N conversation turns (already in
                 brain_ollama._history, but this module provides summaries for
                 the system prompt).

Memory is loaded once at import and flushed to disk after every write.
Thread-safe via a threading.Lock.

Public API
----------
  get_user()         → dict of user profile fields
  set_user(key, val) → persist a profile field (name, location, age, …)
  remember(text)     → add a free-form memory fact
  forget(text)       → fuzzy-delete the closest matching memory
  recall(query)      → fuzzy-search memories, return matching list
  forget_all()       → wipe everything (keeps structure intact)
  context_block()    → formatted string to inject into the system prompt
"""

from __future__ import annotations

import json
import os
import threading
import datetime
import difflib
from pathlib import Path
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# ── Storage location ──────────────────────────────────────────────────────────
_DATA_DIR  = Path(__file__).resolve().parent / "data"
_MEM_FILE  = _DATA_DIR / "memory.json"
_LOCK      = threading.Lock()

# ── Default schema ────────────────────────────────────────────────────────────
_DEFAULT: dict = {
    "user": {
        "name":        "",
        "location":    "",
        "language":    "English",
        "occupation":  "",
        "preferences": {},   # e.g. {"coffee": "black", "music": "Arijit Singh"}
        "details":     {},   # anything else ("I own a dog named Max")
    },
    "memories": [],          # list of {"id", "text", "created_at", "tags"}
    "reminders": [],         # list of {"id", "text", "due_at", "done": bool}
    "session_count": 0,
}


# ── Internal helpers ──────────────────────────────────────────────────────────

def _load() -> dict:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    if _MEM_FILE.exists():
        try:
            with open(_MEM_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Merge missing keys from _DEFAULT
            for k, v in _DEFAULT.items():
                data.setdefault(k, v)
            if "user" in data:
                for k, v in _DEFAULT["user"].items():
                    data["user"].setdefault(k, v)
            return data
        except Exception as e:
            logger.warning(f"[MEMORY] Corrupt memory file, resetting: {e}")
    return json.loads(json.dumps(_DEFAULT))   # deep copy


def _save(store: dict) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(_MEM_FILE, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2, ensure_ascii=False)


# Load once at import
_store: dict = _load()


# ── Public API ─────────────────────────────────────────────────────────────────

def increment_session():
    """Call once per assistant startup."""
    with _LOCK:
        _store["session_count"] = _store.get("session_count", 0) + 1
        _save(_store)


def get_user() -> dict:
    """Return the user profile dict."""
    with _LOCK:
        return dict(_store["user"])


def set_user(key: str, value: str) -> None:
    """
    Persist a top-level user field.
    key can be 'name', 'location', 'occupation', 'language', or any custom key
    which is stored under 'details'.
    """
    TOP_FIELDS = {"name", "location", "language", "occupation"}
    with _LOCK:
        if key in TOP_FIELDS:
            _store["user"][key] = value
        else:
            _store["user"]["details"][key] = value
        _save(_store)
    logger.info(f"[MEMORY] User.{key} = {value!r}")


def set_preference(category: str, value: str) -> None:
    """Store 'I prefer X for Y' type facts under user.preferences."""
    with _LOCK:
        _store["user"]["preferences"][category] = value
        _save(_store)
    logger.info(f"[MEMORY] Preference [{category}] = {value!r}")


def remember(text: str, tags: list[str] | None = None) -> str:
    """
    Store a free-form memory fact.
    Returns a confirmation string suitable for TTS.
    """
    import uuid
    tags = tags or []
    entry = {
        "id":         str(uuid.uuid4())[:8],
        "text":       text.strip(),
        "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "tags":       tags,
    }
    with _LOCK:
        _store["memories"].append(entry)
        # Cap at 200 memories — trim oldest
        if len(_store["memories"]) > 200:
            _store["memories"] = _store["memories"][-200:]
        _save(_store)
    logger.info(f"[MEMORY] Stored: {text!r}")
    return f"Got it, I'll remember that."


def forget(query: str) -> str:
    """
    Remove the memory that best matches *query* (fuzzy match).
    Returns a confirmation or 'not found' string.
    """
    with _LOCK:
        texts = [m["text"] for m in _store["memories"]]
        if not texts:
            return "I don't have any memories stored yet."
        matches = difflib.get_close_matches(query, texts, n=1, cutoff=0.4)
        if not matches:
            return "I couldn't find a memory matching that."
        matched_text = matches[0]
        _store["memories"] = [m for m in _store["memories"] if m["text"] != matched_text]
        _save(_store)
    logger.info(f"[MEMORY] Forgot: {matched_text!r}")
    return f"Okay, I've forgotten that."


def recall(query: str = "", n: int = 5) -> list[str]:
    """
    Return up to *n* memories that best match *query*.
    If query is empty, return the most recent *n* memories.
    """
    with _LOCK:
        memories = list(_store["memories"])

    if not memories:
        return []

    texts = [m["text"] for m in memories]

    if not query.strip():
        return [m["text"] for m in memories[-n:]]

    matches = difflib.get_close_matches(query, texts, n=n, cutoff=0.3)
    if matches:
        return matches

    # Substring fallback
    q = query.lower()
    subset = [t for t in texts if q in t.lower()]
    return subset[:n]


def clear_all() -> str:
    """Wipe all stored memories and user profile data."""
    with _LOCK:
        _store["memories"] = []
        _store["user"]["name"] = ""
        _store["user"]["location"] = ""
        _store["user"]["occupation"] = ""
        _store["user"]["preferences"]= {}
        _store["user"]["details"] = {}
        _save(_store)
    return "Done. I've cleared all my memories and profile data."

# ── Reminders ─────────────────────────────────────────────────────────────────

def add_reminder(text: str, due_at: str) -> None:
    """Add a persistent reminder. due_at should be an ISO timestamp."""
    import uuid
    with _LOCK:
        _store.setdefault("reminders", [])
        entry = {
            "id": str(uuid.uuid4())[:8],
            "text": text.strip(),
            "due_at": due_at,
            "done": False,
            "created_at": datetime.datetime.now().isoformat()
        }
        _store["reminders"].append(entry)
        _save(_store)
    logger.info(f"[MEMORY] Reminder added: '{text}' for {due_at}")

def get_due_reminders() -> list[dict]:
    """Return all reminders that are due but not yet marked done."""
    import datetime
    now = datetime.datetime.now().isoformat()
    due = []
    with _LOCK:
        reminders = _store.get("reminders", [])
        for r in reminders:
            if not r.get("done") and r.get("due_at") <= now:
                due.append(r)
    return due

def mark_reminder_done(reminder_id: str) -> None:
    """Mark a specific reminder as completed."""
    with _LOCK:
        for r in _store.get("reminders", []):
            if r.get("id") == reminder_id:
                r["done"] = True
                break
        _save(_store)
    logger.info(f"[MEMORY] Reminder {reminder_id} marked as done.")


def context_block() -> str:
    """
    Returns a compact memory summary string for injection into the LLM system prompt.
    Kept short (<300 chars) to avoid bloating the context window.
    """
    with _LOCK:
        user = _store["user"]
        mems = _store["memories"]

    parts: list[str] = []

    # User profile
    if user.get("name"):
        parts.append(f"User name: {user['name']}")
    if user.get("location"):
        parts.append(f"Location: {user['location']}")
    if user.get("occupation"):
        parts.append(f"Occupation: {user['occupation']}")
    if user.get("preferences"):
        prefs = ", ".join(f"{k}={v}" for k, v in list(user["preferences"].items())[:5])
        parts.append(f"Preferences: {prefs}")
    if user.get("details"):
        details = "; ".join(f"{k}: {v}" for k, v in list(user["details"].items())[:3])
        parts.append(details)

    # Recent memories (last 8)
    if mems:
        recent = [m["text"] for m in mems[-8:]]
        parts.append("Memories: " + " | ".join(recent))

    result = "\n".join(parts) if parts else ""
    # Hard cap to prevent token bloat — system prompt must stay compact
    if len(result) > 300:
        result = result[:297] + "..."
    return result


def get_greeting() -> str:
    """
    Return a personalized, time-of-day aware, and friendly F.R.I.D.A.Y.-style greeting.
    """
    import random
    from datetime import datetime

    with _LOCK:
        user   = _store["user"]
        prefs  = user.get("preferences", {})
        mems   = _store["memories"]

    name    = user.get("name", "")
    call_me = prefs.get("greeting_title", "")  # e.g. "boss", "sir"

    # 1. Determine title/name preference
    # Check memories for a custom greeting instruction override
    for m in reversed(mems):
        t = m["text"].lower()
        if "call me" in t or "greet me" in t or "wake up" in t:
            for word in m["text"].split():
                if word.lower() not in {"always", "call", "me", "when", "you", "wake",
                                        "up", "greet", "start", "please", "yuki"}:
                    call_me = word.strip(".,!")
                    break

    target_name = call_me or name or "boss"

    # 2. Determine time of day
    hour = datetime.now().hour
    if 5 <= hour < 12:
        period = "morning"
    elif 12 <= hour < 17:
        period = "afternoon"
    elif 17 <= hour < 22:
        period = "evening"
    else:
        period = "night"

    # 3. F.R.I.D.A.Y. inspired friendly greeting banks
    GREETINGS = {
        "morning": [
            f"Top of the morning to you, {target_name}. All systems are nominal.",
            f"Good morning, {target_name}. I've run the diagnostics... we're ready to go.",
            f"Morning, {target_name}! Hope you had a good rest. What's on the agenda?",
            f"The sun is up and so am I. Ready when you are, {target_name}."
        ],
        "afternoon": [
            f"Good afternoon, {target_name}. How is your day progressing?",
            f"Afternoon, {target_name}. I'm synced and ready for your next command.",
            f"Hello, {target_name}. Hope your afternoon is going smoothly.",
            f"Systems online. Good to see you this afternoon, {target_name}."
        ],
        "evening": [
            f"Good evening, {target_name}. Winding down, or just getting started?",
            f"Evening, {target_name}. The day's almost done, but I'm still at 100%.",
            f"Good to see you this evening, {target_name}. How can I help?",
            f"Sunset is approaching, {target_name}. I'm here if you need anything."
        ],
        "night": [
            f"Still working late, {target_name}? Don't forget to get some sleep.",
            f"Night owl mode engaged. I'm with you as long as you need, {target_name}.",
            f"It's getting late, {target_name}. All systems standing by.",
            f"The world is quiet, but I'm wide awake for you, {target_name}."
        ]
    }

    return random.choice(GREETINGS[period])
