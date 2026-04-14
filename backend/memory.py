"""
memory.py — Persistent memory store for Yuki.

Two-layer memory:
  1. Long-term:  JSON file on disk (survives restarts). Stores user profile +
                 facts the user explicitly asked Yuki to remember.
  2. Short-term: In-process ring of the last N conversation turns (already in
                 brain.ollama_brain._history, but this module provides summaries for
                 the system prompt).

Memory is loaded once at import and flushed to disk after every write.
Thread-safe via a threading.Lock.

Public API
----------
  get_user()         → dict of user profile fields
  set_user(key, val) → persist a profile field (name, location, age, …)
  save_fact(text)    → add a free-form memory fact
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
import numpy as np
import asyncio
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Cache for semantic embeddings
_embed_cache = {}

async def get_embedding_async(text: str) -> list[float]:
    """Fetch text embedding from Gemini with local caching."""
    if text in _embed_cache:
        return _embed_cache[text]
        
    try:
        from google import genai
        from backend.config import cfg
        import os
        
        gemini_cfg = cfg.get("gemini", {})
        s_cfg = gemini_cfg.get("google_ai_studio", {})
        api_key = (s_cfg.get("api_key") or os.environ.get("GOOGLE_API_KEY", "")).strip()
        
        if api_key and not api_key.startswith("AQ."):
            client = genai.Client(api_key=api_key)
        else:
            client = genai.Client()
            
        res = await asyncio.to_thread(
            client.models.embed_content,
            model="text-embedding-004",
            contents=text
        )
        
        emb = res.embeddings[0].values
        _embed_cache[text] = emb
        return emb
    except Exception as e:
        logger.debug(f"[MEMORY] Embedding failed: {e}")
        return []

def cosine_similarity(v1, v2) -> float:
    """Compute rapid cosine similarity using Numpy."""
    a = np.array(v1)
    b = np.array(v2)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))

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


def get(key: str, default: any = None) -> any:
    """Generic getter for any top-level key in the memory store."""
    with _LOCK:
        return _store.get(key, default)


def set(key: str, value: any) -> None:
    """Generic setter for any top-level key in the memory store."""
    with _LOCK:
        _store[key] = value
        _save(_store)
    logger.info(f"[MEMORY] Set {key} = {value!r}")


def set_preference(category: str, value: str) -> None:
    """Store 'I prefer X for Y' type facts under user.preferences."""
    with _LOCK:
        _store["user"]["preferences"][category] = value
        _save(_store)
    logger.info(f"[MEMORY] Preference [{category}] = {value!r}")


def save_fact(text: str, tags: list[str] | None = None) -> str:
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
    logger.info(f"[MEMORY] Saved: {text!r}")
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


def get_all_memories() -> list[dict]:
    """Return the raw list of all stored memories."""
    with _LOCK:
        return list(_store["memories"])


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
    Returns a structured context block for high-attention LLM injection.
    Separates user identity, preferences, and long-term facts.
    """
    with _LOCK:
        user = _store["user"]
        mems = _store["memories"]
        session_count = _store.get("session_count", 1)

    sections: list[str] = []
    
    # Session Header
    sections.append(f"[METADATA]\nSession #: {session_count}")

    # User Profile (The core identity)
    profile_parts = []
    if user.get("name"): profile_parts.append(f"Name: {user['name']}")
    if user.get("location"): profile_parts.append(f"Loc: {user['location']}")
    if user.get("preferences"):
        prefs = ", ".join(f"{k}:{v}" for k, v in list(user["preferences"].items())[:8])
        profile_parts.append(f"Prefs: {prefs}")
    
    if profile_parts:
        sections.append("[USER_PROFILE]\n" + "\n".join(profile_parts))

    # Neural Memories (Long-term facts)
    if mems:
        # Show last 10 memories for richer context
        memory_lines = []
        now = datetime.datetime.now()
        for m in mems[-10:]:
            # Add relative time if possible
            try:
                ts = datetime.datetime.fromisoformat(m["created_at"])
                delta = now - ts
                if delta.days > 0: time_str = f"{delta.days}d ago"
                elif delta.seconds > 3600: time_str = f"{delta.seconds//3600}h ago"
                else: time_str = "recent"
                memory_lines.append(f"- ({time_str}) {m['text']}")
            except:
                memory_lines.append(f"- {m['text']}")
        
        sections.append("[NEURAL_MEMORIES]\n" + "\n".join(memory_lines))

    result = "\n\n".join(sections)
    # Neural Economy: Hard cap to prevent context bloat.
    # 3,000 characters is plenty for background context without killing the session.
    if len(result) > 3000:
        result = result[:2997] + "..."
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

    target_name = call_me or name or "Sir"

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


# ── Behavioral Pattern Tracking ───────────────────────────────────────────────

def track_pattern(action: str, hour: int) -> None:
    """
    Record that an action was performed at a given hour.
    Key format: "{action}_{hour}" → count
    Capped at 500 entries to prevent bloat.
    """
    with _LOCK:
        patterns = _store.setdefault("patterns", {})
        key = f"{action}_{hour}"
        patterns[key] = patterns.get(key, 0) + 1
        # Trim if needed: keep highest-count entries
        if len(patterns) > 500:
            sorted_items = sorted(patterns.items(), key=lambda x: x[1], reverse=True)
            _store["patterns"] = dict(sorted_items[:400])
        _save(_store)


def get_patterns() -> dict:
    """Return the full usage pattern dict."""
    with _LOCK:
        return dict(_store.get("patterns", {}))


def get_top_actions_for_hour(hour: int, min_count: int = 3, n: int = 2) -> list[str]:
    """
    Return the top N tools the user most commonly uses at this hour.
    Only returns actions seen at least min_count times (real pattern, not noise).
    """
    with _LOCK:
        patterns = _store.get("patterns", {})

    hour_actions: dict[str, int] = {}
    for key, count in patterns.items():
        if key.endswith(f"_{hour}") and count >= min_count:
            action = key.rsplit("_", 1)[0]
            hour_actions[action] = count

    sorted_actions = sorted(hour_actions.items(), key=lambda x: x[1], reverse=True)
    return [action for action, _ in sorted_actions[:n]]
