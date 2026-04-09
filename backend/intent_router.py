"""
intent_router.py — Fast-path intent matcher for Yuki.

Intercepts ~85% of common commands BEFORE they reach Ollama, resolving them
with pure Python regex + datetime + system calls in < 1 ms.

The router returns a brain-compatible result dict on a match, or None if the
command is complex / conversational and should fall through to the LLM.

Supported intents (English + Hindi/Hinglish):
  open_app     close_app   system_info   set_volume   set_brightness
  screenshot   search_web  play_youtube  get_weather  clipboard_copy
  reminder     none (chit-chat / greetings)

Design principles:
  1. Fastest patterns first (short-circuit on first match).
  2. Normalize once, match many times.
  3. Fuzzy fallback only runs when exact regex misses — adds ~1 ms.
  4. Hindi/Hinglish patterns share the same action handlers as English.
  5. Never import Ollama / Whisper / audio in this module.
"""

from __future__ import annotations

import re
import datetime
import difflib
from typing import Optional
from backend.utils.logger import get_logger
from backend.config import cfg
from backend import memory as mem

logger = get_logger(__name__)

# ── Result helpers ─────────────────────────────────────────────────────────────

def _result(action_type: str, params: dict, response: str) -> dict:
    """Return a brain-schema-compatible result dict."""
    return {
        "needs_clarify": False,
        "action": {"type": action_type, "params": params},
        "response": response,
        "question": None,
        "options": [],
        "_fast_path": True,          # Debug flag — not used by executor
    }

def _none(response: str) -> dict:
    """Pure conversational reply — no action taken."""
    return _result("none", {}, response)


# ── App name lists (for fuzzy matching) ───────────────────────────────────────

_KNOWN_APPS = [
    "chrome", "google chrome", "firefox", "edge", "brave", "opera",
    "notepad", "wordpad", "calculator", "paint", "mspaint",
    "word", "excel", "powerpoint", "outlook", "onenote",
    "spotify", "vlc", "discord", "slack", "teams", "zoom", "telegram",
    "whatsapp", "instagram", "twitter", "x", "youtube",
    "vs code", "vscode", "visual studio code", "pycharm", "android studio",
    "terminal", "cmd", "powershell", "task manager", "file explorer",
    "settings", "control panel", "camera", "photos",
]

# Hindi words → English app names
_HINDI_APP_MAP = {
    "krom":     "chrome",
    "chrom":    "chrome",
    "kalkulétar": "calculator",
    "calculétar": "calculator",
    "notepad":  "notepad",
    "spotify":  "spotify",
    "whatsapp": "whatsapp",
}

# ── Text normalisation ─────────────────────────────────────────────────────────

_PUNCT = re.compile(r"[^\w\s]")

def _normalise(text: str) -> str:
    """Lowercase, strip punctuation, collapse spaces."""
    text = text.lower().strip()
    text = _PUNCT.sub(" ", text)
    return re.sub(r"\s+", " ", text)


# ── Fuzzy app resolution ───────────────────────────────────────────────────────

def _fuzzy_app(raw: str, threshold: float = 0.72) -> Optional[str]:
    """
    Resolve a possibly-misspelled / Hinglish app name to a canonical name.
    Falls back to the raw value if no good match is found.
    """
    raw = raw.strip().lower()
    # Direct hit
    if raw in _KNOWN_APPS:
        return raw
    # Hindi transliteration map
    if raw in _HINDI_APP_MAP:
        return _HINDI_APP_MAP[raw]
    # Fuzzy string match
    matches = difflib.get_close_matches(raw, _KNOWN_APPS, n=1, cutoff=threshold)
    return matches[0] if matches else raw   # return raw so executor can try it


# ── Number extraction helpers ──────────────────────────────────────────────────

_NUM   = re.compile(r"\b(\d{1,3})\b")
_WORDS = {
    "zero":0,"one":1,"two":2,"three":3,"four":4,"five":5,
    "six":6,"seven":7,"eight":8,"nine":9,"ten":10,
    "twenty":20,"thirty":30,"forty":40,"fifty":50,
    "sixty":60,"seventy":70,"eighty":80,"ninety":90,"hundred":100,
}

def _extract_num(text: str, default: Optional[int] = None) -> Optional[int]:
    """Extract the first integer value from text (digits or English words)."""
    m = _NUM.search(text)
    if m:
        return int(m.group(1))
    for word, val in _WORDS.items():
        if word in text:
            return val
    return default

def _extract_minutes(text: str) -> int:
    """Extract delay in minutes from a reminder command."""
    # "in 10 minutes", "after 5 mins", "in an hour"
    m = re.search(r"in (?:an? )?(\d+) ?(min|minute|hour|hr)", text)
    if m:
        val = int(m.group(1))
        unit = m.group(2)
        return val * 60 if "hour" in unit or "hr" in unit else val
    n = _extract_num(text, 5)
    return n if n else 5


# ══════════════════════════════════════════════════════════════════════════════
# Intent pattern library
# Each entry is (compiled_regex, handler_function).
# Patterns are tried IN ORDER — put more specific patterns before general ones.
# ══════════════════════════════════════════════════════════════════════════════

def _handle_open(m: re.Match, text: str) -> dict:
    raw = (m.group("app") or "").strip() or text.replace("open","").replace("launch","").replace("start","").strip()
    
    # If it's a multi-step command like "open chrome and ...", let the agentic AI brain handle it.
    if " and " in raw or " search " in raw or " to " in raw:
        return None  # type: ignore[return-value]

    app = _fuzzy_app(raw)
    return _result("open_app", {"name": app}, f"Opening {app}.")

def _handle_close(m: re.Match, text: str) -> dict:
    raw = (m.group("app") or "").strip()
    app = _fuzzy_app(raw)
    return _result("close_app", {"name": app}, f"Closing {app}.")

def _handle_time(_m, _text) -> dict:
    t = datetime.datetime.now().strftime("%I:%M %p").lstrip("0")
    return _none(f"The time is {t}.")

def _handle_date(_m, _text) -> dict:
    d = datetime.datetime.now().strftime("%A, %B %d")
    return _none(f"Today is {d}.")

def _handle_battery(_m, _text) -> dict:
    return _result("system_info", {"query": "battery"}, "Let me check your battery.")

def _handle_volume_set(m: re.Match, text: str) -> dict:
    level = _extract_num(text, 50)
    return _result("set_volume", {"level": level}, f"Setting volume to {level}.")

def _handle_volume_up(_m, _text) -> dict:
    return _result("set_volume", {"level": "__up10"}, "Turning volume up.")

def _handle_volume_down(_m, _text) -> dict:
    return _result("set_volume", {"level": "__down10"}, "Turning volume down.")

def _handle_mute(_m, _text) -> dict:
    return _result("set_volume", {"level": 0}, "Muting.")

def _handle_brightness_set(m: re.Match, text: str) -> dict:
    level = _extract_num(text, 70)
    return _result("set_brightness", {"level": level}, f"Setting brightness to {level}.")

def _handle_screenshot(_m, _text) -> dict:
    return _result("screenshot", {}, "Taking a screenshot.")

def _handle_search(m: re.Match, text: str) -> dict:
    # Strip the trigger verb to isolate the query
    query = re.sub(
        r"^(search(?: for)?|google|look up|find|bing)\s+",
        "", text, flags=re.I
    ).strip()
    return _result("search_web", {"query": query}, f"Searching for {query}.")

def _handle_youtube(m: re.Match, text: str) -> dict:
    query = re.sub(
        r"^(play|stream|watch)\s+|(\s+on youtube|\s+on yt|\s+youtube)$",
        "", text, flags=re.I
    ).strip()
    return _result("play_youtube", {"query": query, "auto_play": True}, f"Playing {query} on YouTube.")

def _handle_spotify(m: re.Match, text: str) -> dict:
    query = re.sub(
        r"^(play|stream|listen to)\s+|(\s+on spotify|\s+in spotify|\s+spotify)$",
        "", text, flags=re.I
    ).strip()
    return _result("play_spotify", {"query": query}, f"Searching Spotify for {query}.")

def _handle_weather(m: re.Match, text: str) -> dict:
    city_m = re.search(r"(?:in|at|for)\s+([a-z ]+)$", text)
    city   = city_m.group(1).strip() if city_m else "here"
    return _result("get_weather", {"city": city}, f"Getting weather for {city}.")

def _handle_whatsapp(m: re.Match, text: str) -> dict:
    contact_m = re.search(r"(?:to|for)\s+([a-z ]+?)(?:\s+(?:saying|that|:|message))", text)
    msg_m     = re.search(r"(?:saying|that|:)\s+(.+)$", text)
    contact   = contact_m.group(1).strip() if contact_m else ""
    message   = msg_m.group(1).strip() if msg_m else ""
    if not contact:
        # Can't infer contact → let AI handle
        return None  # type: ignore[return-value]
    return _result("send_whatsapp", {"contact": contact, "message": message},
                   f"Sending WhatsApp message to {contact}.")

def _handle_clipboard(m: re.Match, text: str) -> dict:
    content = re.sub(r"^(copy|clipboard copy|put on clipboard)\s+", "", text, flags=re.I).strip()
    content = re.sub(r"\s+to (my )?clipboard$", "", content, flags=re.I).strip()
    return _result("clipboard_copy", {"text": content}, "Copied to clipboard.")

def _handle_reminder(m: re.Match, text: str) -> dict:
    delay   = _extract_minutes(text)
    about_m = re.search(r"(?:to|about|for)\s+(.+)$", text)
    about   = about_m.group(1).strip() if about_m else "something"
    return _result("reminder", {"text": about, "delay_minutes": delay},
                   f"I'll remind you in {delay} minutes.")

def _handle_media_playpause(_m, _text) -> dict:
    return _result("media_controls", {"action": "playpause"}, "Okay.")

def _handle_media_next(_m, _text) -> dict:
    return _result("media_controls", {"action": "next"}, "Next track.")

def _handle_media_prev(_m, _text) -> dict:
    return _result("media_controls", {"action": "previous"}, "Previous track.")

def _handle_greeting(_m, _text) -> dict:
    aname = cfg["assistant"]["name"]
    user  = mem.get_user()
    uname = user.get("name", "")
    now   = datetime.datetime.now().hour
    tod   = "morning" if now < 12 else "afternoon" if now < 17 else "evening"
    greeting = f"Hey {uname}!" if uname else f"Good {tod}!"
    return _none(f"{greeting} How can I help?")

def _handle_thanks(_m, _text) -> dict:
    return _none("You're welcome! Is there anything else?")

def _handle_stop(_m, _text) -> dict:
    return _result("none", {"stop": True}, "Going back to sleep. Say Hey Yuki anytime.")


# ── Memory handlers ───────────────────────────────────────────────────────────

def _handle_remember_fact(m: re.Match, text: str) -> dict:
    """'remember that I have a meeting tomorrow' → store fact."""
    fact = re.sub(
        r"^(remember( that)?|yuki remember|yaad rakh( ki)?|yaad rakho( ki)?)\s+",
        "", text, flags=re.I
    ).strip()
    if not fact:
        return _none("What would you like me to remember?")
    reply = mem.remember(fact)
    return _none(reply)


def _handle_my_name(m: re.Match, text: str) -> dict:
    """'my name is Rahul' → store user name."""
    name_m = re.search(
        r"(?:my name is|i(?:'m| am) called|mera naam(?: hai)?|call me)\s+([a-z][a-z ]{0,30})",
        text, re.I
    )
    if not name_m:
        return None   # type: ignore[return-value]
    name = name_m.group(1).strip().title()
    mem.set_user("name", name)
    return _none(f"Got it! I'll call you {name} from now on.")


def _handle_my_location(m: re.Match, text: str) -> dict:
    """'I live in Mumbai' → store location."""
    loc_m = re.search(
        r"(?:i (?:live|stay|am) in|i'm from|mein(?: rahta)?(?:hun)?|mera city|my city is)\s+([a-z][a-z ]{0,40})",
        text, re.I
    )
    if not loc_m:
        return None  # type: ignore[return-value]
    loc = loc_m.group(1).strip().title()
    mem.set_user("location", loc)
    return _none(f"Got it, I know you're in {loc}.")


def _handle_i_like(m: re.Match, text: str) -> dict:
    """'I like black coffee' / 'I prefer tea' → store preference."""
    # Require at least 3 chars for the object to avoid storing "I like it"
    pref_m = re.search(
        r"(?:i (?:like|love|prefer|enjoy)|mujhe .+ pasand|mujhe .+ chahiye)\s+([a-z0-9\s]{3,})",
        text, re.I
    )
    if not pref_m:
        return None  # type: ignore[return-value]
    pref = pref_m.group(1).strip()
    if pref in ("that", "this", "it", "them"):
        return None # Ignore pronouns
    mem.remember(f"User likes: {pref}")
    return _none(f"Noted! I'll remember you like {pref}.")


def _handle_recall(m: re.Match, text: str) -> dict:
    """'what do you remember about me' / 'what do you know about me'."""
    user  = mem.get_user()
    facts = mem.recall(n=8)
    parts: list[str] = []
    if user.get("name"):
        parts.append(f"Your name is {user['name']}")
    if user.get("location"):
        parts.append(f"you live in {user['location']}")
    if user.get("occupation"):
        parts.append(f"you work as {user['occupation']}")
    if facts:
        parts.append("and I remember: " + ", ".join(facts[:4]))
    if not parts:
        return _none("I don't know much about you yet. Tell me something!")
    return _none(". ".join(parts) + ".")


def _handle_forget_mem(m: re.Match, text: str) -> dict:
    """'forget that I have a meeting' → fuzzy-delete memory."""
    what = re.sub(
        r"^(forget( that)?|yuki forget|bhool jao( ki)?)\s+",
        "", text, flags=re.I
    ).strip()
    reply = mem.forget(what) if what else "What should I forget?"
    return _none(reply)


def _handle_forget_all(_m, _text) -> dict:
    """'clear your memory' / 'forget everything'."""
    return _none(mem.forget_all())


# ── Pattern registry ───────────────────────────────────────────────────────────
# Format: (regex_string, handler)
# Named group "app" used by open/close handlers.

_PATTERNS: list[tuple[str, object]] = [

    # ── Stop  / Sleep ──────────────────────────────────────────────────────────
    (r"^(stop|sleep|go to sleep|nevermind|never mind|cancel|abort|रुको|बंद करो)$",
     _handle_stop),

    # ── Greetings ─────────────────────────────────────────────────────────────
    (r"^(hi|hello|hey|good morning|good afternoon|good evening|namaste|namaskar|hola)[\s!.]*$",
     _handle_greeting),

    # ── Thanks ────────────────────────────────────────────────────────────────
    (r"^(thanks|thank you|dhanyawad|shukriya|thank u|thx|ty)[\s!.]*$",
     _handle_thanks),

    # ── Screenshot ────────────────────────────────────────────────────────────
    (r"(take (a )?screenshot|screenshot le|screenshot lo|capture screen|screen capture)",
     _handle_screenshot),

    # ── Time ──────────────────────────────────────────────────────────────────
    (r"(what('?s| is) the (current )?time|time (batao|bolo|kya hai)|abhi (kya|kitna) baj)",
     _handle_time),

    # ── Date ──────────────────────────────────────────────────────────────────
    (r"(what('?s| is) (today'?s? )?date|aaj ki (date|tarikh)|date (batao|kya hai))",
     _handle_date),

    # ── Battery ───────────────────────────────────────────────────────────────
    (r"(battery (level|percent|status|kitna)|how much battery|kitni battery)",
     _handle_battery),

    # ── Volume — mute ─────────────────────────────────────────────────────────
    (r"(^mute$|mute (the )?(sound|audio|volume)|silent kar|silent mode|awaaz band)",
     _handle_mute),

    # ── Volume — up ───────────────────────────────────────────────────────────
    (r"(volume (up|badhao|increase|tez kar|zyada kar)|increase (the )?volume|louder)",
     _handle_volume_up),

    # ── Volume — down ─────────────────────────────────────────────────────────
    (r"(volume (down|kam karo|decrease|kam kar|thoda kam)|decrease (the )?volume|quieter|softer)",
     _handle_volume_down),

    # ── Volume — set to N ─────────────────────────────────────────────────────
    (r"(set (the )?volume (to )?|volume (set to )?)\d",
     _handle_volume_set),

    # ── Brightness ────────────────────────────────────────────────────────────
    (r"(set (the )?brightness (to )?|brightness (set to )?|screen brightness)\d",
     _handle_brightness_set),

    # ── WhatsApp ──────────────────────────────────────────────────────────────
    (r"(send (a )?whatsapp( message)? to|whatsapp (pe|par|ko)|message .+ on whatsapp)",
     _handle_whatsapp),

    # ── YouTube ───────────────────────────────────────────────────────────────
    (r"(play .+ on (youtube|yt)|youtube pe .+ chalao|youtube par play|watch .+ on youtube)",
     _handle_youtube),

    # ── Spotify ───────────────────────────────────────────────────────────────
    (r"(play .+ on spotify|play .+ in spotify|spotify pe .+ chalao|spotify par play)",
     _handle_spotify),

    # ── Weather ───────────────────────────────────────────────────────────────
    (r"(what'?s? the weather|weather (in|at|for|kya hai)|mausam (kaisa|batao))",
     _handle_weather),

    # ── Web search ────────────────────────────────────────────────────────────
    (r"^(search( for)?|google|look up|find|bing)\s+.+",
     _handle_search),

    # ── Clipboard ─────────────────────────────────────────────────────────────
    (r"(copy .+ to (my )?clipboard|clipboard copy|put .+ on (the )?clipboard)",
     _handle_clipboard),

    # ── Reminder ──────────────────────────────────────────────────────────────
    (r"(remind me (in|after|to)|set a? reminder|याद दिलाओ)",
     _handle_reminder),

    # ── Memory — recall everything ─────────────────────────────────────────────
    (r"(what do you (know|remember) about me|tell me what you know|what have i told you|mera kya pata hai)",
     _handle_recall),

    # ── Memory — forget specific ──────────────────────────────────────────────
    (r"^(forget( that)?|yuki forget|bhool jao)\s+.+",
     _handle_forget_mem),

    # ── Memory — forget all ───────────────────────────────────────────────────
    (r"(clear (your|all) memory|forget everything|reset memory|sab bhool jao)",
     _handle_forget_all),

    # ── Memory — store name ───────────────────────────────────────────────────
    (r"(my name is|i(?:'m| am) called|mera naam(?: hai)?|call me)\s+[a-z]",
     _handle_my_name),

    # ── Memory — store location ───────────────────────────────────────────────
    (r"(i (?:live|stay|am) in|i'?m from|mein rahta|my city is)\s+[a-z]",
     _handle_my_location),

    # ── Memory — preferences ──────────────────────────────────────────────────
    (r"(i (like|love|prefer|enjoy)|mujhe .+ pasand hai)",
     _handle_i_like),

    # ── Memory — store arbitrary fact ─────────────────────────────────────────
    (r"^(remember( that)?|yuki remember|yaad rakh( ki)?|yaad rakho( ki)?)\s+.+",
     _handle_remember_fact),

    # ── Media Controls ────────────────────────────────────────────────────────
    (r"(pause( the)? music|pause|stop( the)? music|pause song|gaana band karo|music band karo|play( the)? music|resume( the)? music|play song|gaana chalao)",
     _handle_media_playpause),

    (r"(next( song| track)?|skip( song| track)?|agla gaana(?: lagao| chalao| bajao)?|change( the)? song|change( the)? track)",
     _handle_media_next),

    (r"(previous( song| track)?|last( song| track)?|peeche wala gaana|pichla gaana|go back)",
     _handle_media_prev),

    # ── Close active window ───────────────────────────────────────────────────
    (r"(close (this|the active|the current) (window|app)?|band (kar do|kardo))",
     lambda m, text: _result("close_app", {"name": "active"}, "Closing the active window.")),

    # ── Close app — English + Hindi (before open, more specific) ────────────
    (r"(close|quit|exit|kill|band karo|band kar)\s+(?P<app>[a-z][a-z0-9 ]{1,30})",
     _handle_close),

    # ── Open app — English ────────────────────────────────────────────────────
    (r"(open|launch|start|run|chala|chalao|kholo|kholdo|open karo)\s+(?P<app>[a-z][a-z0-9 ]{1,30})",
     _handle_open),
]

# Compile all patterns once at import time
_COMPILED: list[tuple[re.Pattern, object]] = [
    (re.compile(pat, re.IGNORECASE), handler)
    for pat, handler in _PATTERNS
]


# ── Public API ─────────────────────────────────────────────────────────────────

def route(text: str) -> Optional[dict]:
    """
    Try to match *text* against the fast-path pattern library.

    Returns:
        A brain-compatible result dict if matched, None if the query should
        be sent to the LLM.
    """
    if not cfg.get("router", {}).get("enabled", True):
        return None  # Fast path disabled in config

    norm = _normalise(text)
    if not norm:
        return None

    for pattern, handler in _COMPILED:
        m = pattern.search(norm)
        if m:
            try:
                result = handler(m, norm)  # type: ignore[call-arg]
                if result is not None:
                    logger.info(f"[FAST PATH] '{norm}' → {result['action']['type']}")
                    return result
            except Exception as e:
                logger.warning(f"[FAST PATH] handler error for '{norm}': {e}")
                return None  # Fall through to AI on handler error

    logger.debug(f"[FAST PATH] No match for '{norm}' — routing to AI")
    return None
