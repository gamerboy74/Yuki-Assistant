"""
brain/reasoning.py — Yuki's autonomous reasoning engine.

Implements JARVIS-style intelligence entirely in Python.
Zero LLM tokens. Runs before every API call.

Pipeline:
  1. Classify the user's REAL intent (not just literal words)
  2. Build an execution plan (tool chain hint)
  3. Pull semantically relevant memories
  4. Detect proactive opportunity
  5. Return an enriched context string to inject into the user turn

The plan hint collapses what would be 2-3 agentic LLM rounds into 1,
saving ~1,500-3,000 tokens per complex request.
"""

from __future__ import annotations

import re
import datetime
from dataclasses import dataclass, field
from backend.utils.logger import get_logger

logger = get_logger(__name__)


# ── Global State ────────────────────────────────────────────────────────────
# Simplified world state tracking for pronouns like "it"
_REASONING_STATE = {
    "last_file": None,
    "last_app": None
}


# ── Intent Categories ────────────────────────────────────────────────────────

class Intent:
    BROWSER_SEARCH    = "BROWSER_SEARCH"
    BROWSER_NAVIGATE  = "BROWSER_NAVIGATE"
    BROWSER_READ      = "BROWSER_READ"
    APP_OPEN          = "APP_OPEN"
    APP_CLOSE         = "APP_CLOSE"
    APP_TYPE          = "APP_TYPE"        # open app → type something
    MEDIA_SPOTIFY     = "MEDIA_SPOTIFY"
    MEDIA_YOUTUBE     = "MEDIA_YOUTUBE"
    FILE_READ         = "FILE_READ"
    FILE_WRITE        = "FILE_WRITE"
    DESIGN_PAGE       = "DESIGN_PAGE"
    SYSTEM_CONTROL    = "SYSTEM_CONTROL"  # volume, brightness, power
    SYSTEM_INFO       = "SYSTEM_INFO"     # battery, cpu, ram
    WEATHER           = "WEATHER"
    WHATSAPP          = "WHATSAPP"
    SCREENSHOT        = "SCREENSHOT"
    SCREEN_ANALYZE    = "SCREEN_ANALYZE"
    REMINDER          = "REMINDER"
    MEMORY_STORE      = "MEMORY_STORE"
    MEMORY_RECALL     = "MEMORY_RECALL"
    CODE_HELP         = "CODE_HELP"       # Analyze screen errors + Fix file
    COMPLEX_TASK      = "COMPLEX_TASK"    # multi-step: write email and send it
    CONVERSATIONAL    = "CONVERSATIONAL"
    UNKNOWN           = "UNKNOWN"

# ── Safety Impact Metadata ──────────────────────────────────────────────────
# Intens that require a "Verbal Handshake" or explicit caution.
HIGH_IMPACT_INTENTS = {
    Intent.SYSTEM_CONTROL,  # Power / Restart
    Intent.FILE_WRITE,      # Overwriting data
    Intent.WHATSAPP,        # Social messaging
    Intent.COMPLEX_TASK,    # Potential for deep automation loops
}


# ── Intent Classification Rules ──────────────────────────────────────────────
# Ordered from most to least specific. First match wins.

_INTENT_RULES: list[tuple[re.Pattern, str]] = [
    # Complex Cross-App Pipelines — Primary Brain Logic
    (re.compile(r"(find|search|look up).*(and|then).*(save|write|note|text|msg|whatsapp|send|summarize|analyze)", re.I), Intent.COMPLEX_TASK),
    (re.compile(r"(open|launch|go to).*(and|then).*(type|write|click|search|read|extract|scrape)", re.I),        Intent.COMPLEX_TASK),
    (re.compile(r"(read|what does|whats on|check).*(and|then).*(summarize|tell|write|save|compare|verify)", re.I),     Intent.COMPLEX_TASK),
    (re.compile(r"(take.*screenshot|capture).*(and|then).*(analyze|look|see|tell|describe|find|click)", re.I), Intent.COMPLEX_TASK),
    (re.compile(r"(research|analyze|investigate|deep dive into).*", re.I), Intent.COMPLEX_TASK),

    # Browser
    (re.compile(r"(open|go to|navigate|visit|open url|browser.*open)\s+(https?://|[a-zA-Z0-9-]+\.[a-z]{2,})", re.I), Intent.BROWSER_NAVIGATE),
    (re.compile(r"(search|google|look up|find|what is|who is|how to|latest|kya hai|batao)\b", re.I), Intent.BROWSER_SEARCH),
    (re.compile(r"(read|what does|whats on|content of|summarize).*(page|tab|site|article)", re.I),   Intent.BROWSER_READ),

    # Media
    (re.compile(r"(play|song|music|artist|track|album|spotify|gaana|bajao)\b", re.I), Intent.MEDIA_SPOTIFY),
    (re.compile(r"(youtube|video|watch|dekh|streaming)\b", re.I),                     Intent.MEDIA_YOUTUBE),

    # WhatsApp
    (re.compile(r"(whatsapp|message|msg|send.*to|text.*to)\b", re.I), Intent.WHATSAPP),

    # Site navigation fallback: "open cricbuzz" -> BROWSER_NAVIGATE (detect site-like names)
    (re.compile(r"(open|go to|visit)\s+([a-zA-Z0-9-]+)(?:\s+and|\s+then|$)", re.I), Intent.BROWSER_NAVIGATE),

    # App control
    (re.compile(r"(type|write|paste|likhna|likho|type this)\b", re.I), Intent.APP_TYPE),
    (re.compile(r"(open|launch|start|chalu|kholo)\s+\w+", re.I),       Intent.APP_OPEN),
    (re.compile(r"(close|kill|quit|band karo|exit)\s+\w+", re.I),      Intent.APP_CLOSE),

    # File ops
    (re.compile(r"(design|create|make|build|html|webpage|tailwind|landing)", re.I), Intent.DESIGN_PAGE),
    (re.compile(r"(read|open|show)\s+(file|document|pdf|folder)", re.I),            Intent.FILE_READ),
    (re.compile(r"(write|save|create)\s+(file|note|document)", re.I),               Intent.FILE_WRITE),

    # System
    (re.compile(r"(shutdown|restart|sleep|lock|hibernate|band karo system)", re.I), Intent.SYSTEM_CONTROL),
    (re.compile(r"(volume|sound|mute|loud|quiet)", re.I),                           Intent.SYSTEM_CONTROL),
    (re.compile(r"(brightness|screen.*light|dim)", re.I),                           Intent.SYSTEM_CONTROL),
    (re.compile(r"(battery|cpu|ram|memory|how.*system|system.*status)", re.I),      Intent.SYSTEM_INFO),

    # Utilities
    (re.compile(r"(weather|temperature|forecast|mausam|barish)", re.I),     Intent.WEATHER),
    (re.compile(r"(screenshot|capture.*screen|snap)", re.I),                Intent.SCREENSHOT),
    (re.compile(r"(look at|see|whats on|describe.*screen|screen mein)", re.I), Intent.SCREEN_ANALYZE),
    (re.compile(r"(remind|reminder|alarm|notify me|yaad dilao)", re.I),     Intent.REMINDER),
    (re.compile(r"(remember|save this|note|store|yaad rakh)", re.I),        Intent.MEMORY_STORE),
    (re.compile(r"(what do you know|recall|memory|yaad hai|you remember)", re.I), Intent.MEMORY_RECALL),
    (re.compile(r"(fix.*(error|code|bug)|what.*is.*wrong|why.*is.*this.*not.*working|analyze.*code)", re.I), Intent.CODE_HELP),
]


def classify_intent(transcript: str) -> str:
    """Classify the user's real intent. Returns an Intent constant."""
    for pattern, intent in _INTENT_RULES:
        if pattern.search(transcript):
            return intent
    return Intent.UNKNOWN


# ── Tool Plan Builder ────────────────────────────────────────────────────────
# Generates the shortest tool chain for each intent.
# This hint is injected into the user message so the LLM
# executes immediately instead of spending a full round figuring it out.

def _extract_query(transcript: str) -> str:
    """Strip command words to get the core query/subject."""
    stop_words = r"^(search for|google|look up|find|what is|who is|play|open|launch|set|check|tell me about|show me)\s+"
    return re.sub(stop_words, "", transcript, flags=re.I).strip()


def _extract_app(transcript: str) -> str:
    """Try to extract the app name from the transcript."""
    m = re.search(r"(?:open|launch|start|close|kill)\s+([a-zA-Z0-9\s]+?)(?:\s+and|\s+then|$)", transcript, re.I)
    return m.group(1).strip() if m else ""


def _extract_city(transcript: str, user_location: str) -> str:
    """Extract city name or fall back to user's stored location."""
    # Try to find a city in the transcript
    m = re.search(r"(?:weather|temperature|forecast)\s+(?:in|at|for)?\s*([a-zA-Z\s]+?)(?:\?|$)", transcript, re.I)
    if m:
        return m.group(1).strip()
    return user_location or "current location"


def _extract_site(transcript: str) -> str | None:
    """
    Intelligently extract a site name or URL from the transcript.
    If it's a naked name like 'cricbuzz', it appends '.com'.
    """
    # 1. Look for explicit URLs
    m = re.search(r"(https?://\S+|[a-zA-Z0-9-]+\.[a-z]{2,})", transcript, re.I)
    if m:
        return m.group(1)
    
    # 2. Look for "open [site]" patterns
    m = re.search(r"(?:open|go to|navigate|visit|watch|on)\s+([a-zA-Z0-9-]+)(?:\s+and|\s+then|$)", transcript, re.I)
    if m:
        site = m.group(1).lower()
        if site not in ["app", "file", "folder", "spotify", "youtube", "whatsapp"]:
            return f"{site}.com"
    
    return None


def build_plan(transcript: str, intent: str, user_location: str = "Bhubaneswar") -> str | None:
    """
    Return a compact plan hint string for the given intent.
    Returns None if no plan hint is needed (conversational, unknown).
    """
    q = _extract_query(transcript)
    app = _extract_app(transcript)
    site = _extract_site(transcript)

    # [NEXUS_PLAN_HINT] Collapses multiple agent turns into one.
    plans = {
        Intent.SYSTEM_INFO:      "[RECON: tactical_report()] -> [SYNTHESIZE: holistic diagnostic]",
        Intent.BROWSER_SEARCH:   f"[RECON: search_internet({q!r})] -> [EXECUTE: read_active_tab()]",
        Intent.BROWSER_NAVIGATE: f"[RECON: browser_navigate({site or 'url'!r})] -> [VALIDATE: read_active_tab()]",
        Intent.BROWSER_READ:     "[RECON: read_active_tab()] -> [THINK: synthesize summary]",
        Intent.APP_OPEN:         f"[EXECUTE: open_app({app!r})]",
        Intent.APP_CLOSE:        f"[EXECUTE: close_app({app!r})]",
        Intent.APP_TYPE:         f"[PROTOCOL_AUTO: 1. open_app(tgt) 2. type_text(data) 3. media_controls(play)]",
        Intent.MEDIA_SPOTIFY:    f"[AUTO: play_spotify({q!r})] -> [MONITOR: verify playback]",
        Intent.MEDIA_YOUTUBE:    f"[AUTO: play_youtube({q!r})]",
        Intent.WHATSAPP:         "[EXECUTE: send_whatsapp(contact, msg)]",
        Intent.DESIGN_PAGE:      "[BRAIN_DREAM: design_web_page(full_html)] -> [EXECUTE: open_file(path)]",
        Intent.FILE_READ:        "[RECON: read_file(path)]",
        Intent.FILE_WRITE:       "[EXECUTE: write_file(path, content)]",
        Intent.SYSTEM_CONTROL:   "[EXECUTE: system_control(action)]",
        Intent.WEATHER:          f"[RECON: get_weather({_extract_city(transcript, user_location)!r})]",
        Intent.SCREENSHOT:       "[EXECUTE: screenshot()]",
        Intent.SCREEN_ANALYZE:   "[RECON: analyze_screen(query={q!r})] -> [PIVOT: computer_hands(click_at, x, y)]",
        Intent.REMINDER:         "[EXECUTE: set_reminder(text, delay)]",
        Intent.MEMORY_STORE:     "[BRAIN_SAVE: mem.save_fact(fact)]",
        Intent.MEMORY_RECALL:    "[RECON: mem.context_block()]",
        Intent.CODE_HELP:        "[MISSION: 1. analyze_screen(error) 2. read_file(target) 3. synthesize_fix() 4. write_file(fix)]",
        Intent.COMPLEX_TASK:     "[NEXUS_LOOP: 1. Scan Environment 2. Sequentially build tool-chain 3. Verify final state]",
    }

    return plans.get(intent)


# ── Semantic Memory Retriever ────────────────────────────────────────────────

async def get_relevant_memories_async(transcript: str, memories: list[dict], n: int = 3) -> list[str]:
    """
    Return the top N memories most relevant to this transcript.
    Uses semantic embeddings with keyword fallback.
    """
    if not memories:
        return []

    # Semantic RAG
    try:
        from backend.memory import get_embedding_async, cosine_similarity
        q_emb = await get_embedding_async(transcript)

        if q_emb is not None and len(q_emb) > 0:
            scored = []
            for m in memories:
                t_emb = await get_embedding_async(m["text"])
                if t_emb is not None and len(t_emb) > 0:
                    score = cosine_similarity(q_emb, t_emb)
                    scored.append((score, m["text"]))

            if scored:
                scored.sort(key=lambda x: x[0], reverse=True)
                res = [text for score, text in scored if score > 0.45]
                if res:
                    return res[:n]
    except Exception as e:
        logger.debug(f"[REASONING] RAG failed, falling back to keyword: {e}")

    # Tokenize transcript, strip common stop words
    stop = {"a", "an", "the", "is", "in", "on", "at", "to", "for", "of",
            "and", "or", "it", "my", "me", "you", "i", "this", "that", "what"}
    words = set(transcript.lower().split()) - stop

    if not words:
        return [m["text"] for m in memories[-n:]]

    scored = []
    for m in memories:
        mem_words = set(m["text"].lower().split()) - stop
        overlap = len(words & mem_words)
        if overlap > 0:
            scored.append((overlap, m["text"]))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [text for _, text in scored[:n]]


# ── Proactive Opportunity Detector ───────────────────────────────────────────

_ACTION_READABLE = {
    "play_spotify":     "music on Spotify",
    "get_weather":      "the local weather",
    "search_internet":  "the web for news",
    "open_app":         "your standard workspace",
    "system_info":      "a quick system diagnostic",
    "read_active_tab":  "the open browser content",
    "play_youtube":     "your YouTube feed",
}

_PROACTIVE_TEMPLATES = [
    "Sir, you usually check {readable} around this time. Shall I prepare that for you?",
    "I've noticed a pattern, Sir. You usually {readable} now. Would you like me to go ahead?",
    "It's that time again, Sir. You typically {readable} about now. Ready when you are.",
    "Systems are nominal, Sir. Since you usually {readable} at this hour, I've got it standing by. Just say the word.",
]


def get_proactive_suggestion(patterns: dict) -> str | None:
    """
    Returns a proactive suggestion based on learned usage patterns.
    High-fidelity phrasing for F.R.I.D.A.Y. class interaction.
    """
    import random
    hour = datetime.datetime.now().hour

    # Build hour-specific pattern counts
    hour_actions: dict[str, int] = {}
    for key, count in patterns.items():
        if key.endswith(f"_{hour}") and count >= 3:
            action = key.rsplit("_", 1)[0]
            hour_actions[action] = count

    if not hour_actions:
        return None

    # Pick the most frequent one
    top_action = max(hour_actions, key=hour_actions.get)
    readable = _ACTION_READABLE.get(top_action, top_action.replace("_", " "))
    
    # Selection of "Classy" Greeting
    greeting = ""
    if 5 <= hour < 12: greeting = "Good morning, Sir. "
    elif 12 <= hour < 17: greeting = "Good afternoon, Sir. "
    elif 17 <= hour < 22: greeting = "Good evening, Sir. "
    else: greeting = "Working late, Sir? "

    template = random.choice(_PROACTIVE_TEMPLATES)
    # Remove "Sir," from template if greeting already has "Sir"
    if "Sir" in greeting:
        template = template.replace("Sir, ", "").replace(", Sir", "")
        
    return f"{greeting}{template.format(readable=readable)}"


# ── Turn Context Builder ─────────────────────────────────────────────────────
# This is the main function called by the brain before every API call.

@dataclass
class ReasoningResult:
    intent: str
    plan: str | None
    relevant_memories: list[str]
    is_high_impact: bool      # Flag for safety sentinel
    enriched_transcript: str   # what actually gets sent to the LLM


async def reason_async(transcript: str, all_memories: list[dict], user_location: str = "") -> ReasoningResult:
    """
    Full async reasoning pipeline. Returns an enriched transcript with plan hints
    and relevant context injected. This is what the LLM receives.
    """
    intent = classify_intent(transcript)
    plan   = build_plan(transcript, intent, user_location)
    mems   = await get_relevant_memories_async(transcript, all_memories)
    
    is_high_impact = intent in HIGH_IMPACT_INTENTS

    sections = [f"SIR_INPUT: {transcript}"]
    
    briefing = []
    if plan: briefing.append(f"Mission: {plan}")
    if is_high_impact: briefing.append("Alert: HIGH-IMPACT active.")
    if mems: briefing.append(f"Context: {' | '.join(mems)}")

    if briefing:
        sections.append(f"[TACTICAL_BRIEFING: {' | '.join(briefing)}]")

    enriched = "\n".join(sections)

    logger.debug(f"[REASONING] Intent={intent} | High-Impact={is_high_impact} | Plan={'yes' if plan else 'no'}")

    return ReasoningResult(
        intent=intent,
        plan=plan,
        relevant_memories=mems,
        is_high_impact=is_high_impact,
        enriched_transcript=enriched,
    )


# ── Usage Pattern Tracker ─────────────────────────────────────────────────────

def track_execution(tool_name: str) -> None:
    """
    Call this after every successful tool execution.
    Records the action + current hour for pattern learning.
    """
    try:
        from backend import memory as mem
        hour = datetime.datetime.now().hour
        mem.track_pattern(tool_name, hour)
    except Exception as e:
        logger.debug(f"[REASONING] Pattern track failed: {e}")