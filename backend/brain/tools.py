"""
brain/tools.py — Dynamic Plugin-based Tool Registry for Yuki.

This module now pulls schemas directly from the Plugin Registry, 
ensuring zero redundancy and perfect alignment between capabilities 
and execution.
"""

import re
from typing import Any
from backend.utils.logger import get_logger
from backend.plugins import get_all_plugins

logger = get_logger(__name__)

# ── Tool Selection Logic ──────────────────────────────────────────────────────

# Core tools are ALWAYS included (~300 tokens overhead)
# These are genuinely useful on every turn.
CORE_PLUGINS = [
    "system_info", "open_app", "close_app", "get_weather",
]

# Keyword → additional plugin names to include
_KEYWORD_ROUTES: list[tuple[re.Pattern, list[str]]] = [
    (re.compile(r"whatsapp|message|text|msg|send.*to", re.I),
     ["send_whatsapp", "send_whatsapp_file"]),

    (re.compile(r"file|read|write|document|pdf|pptx?|docx?|save|create.*file|open.*file", re.I),
     ["read_file", "write_file", "find_file", "open_file"]),

    (re.compile(r"screenshot|screen\s*shot|capture|snap", re.I),
     ["screenshot"]),

    (re.compile(r"volume|loud|quiet|mute|sound|media|control|pause|resume|skip|next|back", re.I),
     ["set_volume", "media_controls"]),

    (re.compile(r"bright|dim|screen.*light", re.I),
     ["set_brightness"]),

    (re.compile(r"shutdown|restart|sleep|lock|power\s*(off|down)", re.I),
     ["system_control"]),

    (re.compile(r"remind|reminder|alarm|timer|notify.*later", re.I),
     ["set_reminder"]),

    (re.compile(r"news|headline|latest", re.I),
     ["latest_news", "search_internet"]),

    (re.compile(r"search|find|look up|what is|who is|google|internet", re.I),
     ["search_internet"]),

    (re.compile(r"design|webpage|web\s*page|html|tailwind|ui|landing\s*page|banao|page|type|write|keyboard|likho", re.I),
     ["design_web_page", "write_file", "type_text"]),

    (re.compile(r"navigate|click|button|focus", re.I),
     ["smart_navigate", "browser_click", "browser_navigate"]),

    (re.compile(r"fetch|http|api|url|download", re.I),
     ["http_get"]),

    (re.compile(r"chrome|browser|search.*in|read.*page|scroll|navigate|open|click|.*\.(com|net|to|org|io|in|edu|gov)", re.I),
     ["browser_scroll", "browser_click", "read_active_tab", "browser_navigate", "search_internet"]),

    (re.compile(r"my\s*(name|info|preference|detail|fact)", re.I),
     ["get_user_info"]),
     
    (re.compile(r"remember|save.*fact|keep.*mind|store.*memory", re.I),
     ["save_memory"]),
     
    (re.compile(r"recall|find.*memory|search.*memory|what.*i.*told|what.*did.*i.*say", re.I),
     ["recall_memory"]),
      
    (re.compile(r"spotify|youtube|music|song|artist|play.*music|video|watch|anime", re.I),
     ["play_spotify", "play_youtube", "browser_navigate", "search_internet"]),
      
    (re.compile(r"vision|see|look|describe|what.*is.*this|camera", re.I),
     ["analyze_screen"]),
]

def get_tools_for_query(transcript: str) -> list[dict]:
    """
    Return only the tools relevant to this query, dynamically generated from plugins.
    """
    all_plugins = get_all_plugins()
    if not all_plugins:
        return []

    # Start with core set
    selected_names = set(CORE_PLUGINS)

    # Match keyword routes
    for pattern, plugin_names in _KEYWORD_ROUTES:
        if pattern.search(transcript):
            selected_names.update(plugin_names)

    # Build function schemas
    tools = []
    for name in selected_names:
        plugin = all_plugins.get(name)
        if plugin:
            tools.append(plugin.to_tool_schema())

    logger.debug(f"[TOOLS] Dynamically selected {len(tools)} tools for query.")
    return tools

def get_all_tools() -> list[dict]:
    """Return all available plugins as tools."""
    all_plugins = get_all_plugins()
    return [p.to_tool_schema() for p in all_plugins.values()]

