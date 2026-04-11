"""
brain/tools.py — Selective Tool Registry for Yuki.

Instead of sending ALL 25 tools on every API call (~2,000 tokens),
this module routes tools based on transcript keywords.

Token savings: ~1,500 tokens per call for non-tool queries.
"""

import re
from typing import Any
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# ── Full Tool Definitions ─────────────────────────────────────────────────────
# Defined once, referenced by name in the selector.

_ALL_TOOLS: list[dict[str, Any]] = [
    {"type": "function", "function": {"name": "system_info", "description": "Get system info: time, date, battery, cpu, or ram.", "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "time, date, battery, cpu, ram"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "set_volume", "description": "Set system volume (0-100)", "parameters": {"type": "object", "properties": {"level": {"type": "integer"}}, "required": ["level"]}}},
    {"type": "function", "function": {"name": "set_brightness", "description": "Set brightness (0-100)", "parameters": {"type": "object", "properties": {"level": {"type": "integer"}}, "required": ["level"]}}},
    {"type": "function", "function": {"name": "open_app", "description": "Open a native Windows application (e.g., 'Notepad', 'Calculator', 'File Explorer').", "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "open_file", "description": "Open a specific file locally (e.g., 'notes.txt', 'my_doc.pdf'). Yuki handles the path resolution.", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "The name or path of the file to open"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "close_app", "description": "Close app by name or 'active' window", "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "search_internet", "description": "Search web for facts/news", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "media_controls", "description": "Media: playpause, next, previous", "parameters": {"type": "object", "properties": {"action": {"type": "string", "enum": ["playpause", "next", "previous"]}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "get_weather", "description": "Get weather. Leave city empty for user's current location.", "parameters": {"type": "object", "properties": {"city": {"type": "string", "description": "City name, or leave empty/omitted for auto IP detection"}}, "required": []}}},
    {"type": "function", "function": {"name": "play_youtube", "description": "Play matching video on YouTube", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "play_spotify", "description": "Play artist/song on Spotify", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "latest_news", "description": "Get latest news headlines", "parameters": {"type": "object", "properties": {"topic": {"type": "string"}}, "required": ["topic"]}}},
    {"type": "function", "function": {"name": "screenshot", "description": "Take screen screenshot", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "http_get", "description": "Fetch data from URL", "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}},
    {"type": "function", "function": {"name": "find_file", "description": "Search local files by name", "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "system_control", "description": "Shutdown/Restart/Sleep/Lock PC", "parameters": {"type": "object", "properties": {"action": {"type": "string", "enum": ["shutdown", "restart", "sleep", "lock"]}, "confirm": {"type": "boolean"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "set_reminder", "description": "Set future reminder", "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "delay_minutes": {"type": "number"}}, "required": ["text", "delay_minutes"]}}},
    {"type": "function", "function": {"name": "type_text", "description": "Type text verbatim", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "get_user_info", "description": "Get personal facts", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "read_file", "description": "Read file contents (text, pdf, docx, pptx)", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "write_file", "description": "Save text/code to a file. Use a filename only (e.g., 'notes.txt'), Yuki handles the path.", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Filename or simple relative path"}, "content": {"type": "string"}, "mode": {"type": "string", "enum": ["overwrite", "append"]}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "send_whatsapp", "description": "WhatsApp text to contact", "parameters": {"type": "object", "properties": {"contact": {"type": "string"}, "message": {"type": "string"}}, "required": ["contact", "message"]}}},
    {"type": "function", "function": {"name": "send_whatsapp_file", "description": "Send file via WhatsApp contact", "parameters": {"type": "object", "properties": {"contact": {"type": "string"}, "file_name": {"type": "string"}}, "required": ["contact", "file_name"]}}},
    {"type": "function", "function": {"name": "search_in_chrome", "description": "Search in Chrome & return info", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "smart_navigate", "description": "Navigate app UI tree", "parameters": {"type": "object", "properties": {"target": {"type": "string"}, "action": {"type": "string", "enum": ["click", "focus", "list"]}}, "required": ["target"]}}},
    {"type": "function", "function": {"name": "design_web_page", "description": "Generate premium UI (Tailwind). Use a slug/name for 'path' (e.g. 'landing_page').", "parameters": {"type": "object", "properties": {"content": {"type": "string"}, "path": {"type": "string", "description": "Slug or filename for the design"}}, "required": ["content"]}}},
    {"type": "function", "function": {"name": "read_active_tab", "description": "Extract ALL visible text from the current browser page. Use this to summarize articles, read news, or analyze website content.", "parameters": {"type": "object", "properties": {"max_chars": {"type": "integer", "default": 4000}}}}},
    {"type": "function", "function": {"name": "browser_navigate", "description": "Navigate the browser to a specific URL. Required before using read_active_tab for a specific site.", "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}},
    {"type": "function", "function": {"name": "browser_click", "description": "Click an element (link, button) by its text or CSS selector.", "parameters": {"type": "object", "properties": {"target": {"type": "string"}}, "required": ["target"]}}},
    {"type": "function", "function": {"name": "get_page_elements", "description": "List clickable elements on the current page. Helps you know what can be clicked.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "browser_scroll", "description": "Scroll the active browser page.", "parameters": {"type": "object", "properties": {"direction": {"type": "string", "enum": ["up", "down"]}}, "required": ["direction"]}}},
]

# Build name → tool lookup
_TOOL_INDEX: dict[str, dict] = {
    t["function"]["name"]: t for t in _ALL_TOOLS
}


# ── Tool Groups ──────────────────────────────────────────────────────────────
# Core tools are ALWAYS included (~8 tools, ~640 tokens — down from ~2,000)
# Extended tools are only added when keywords match.

CORE_TOOLS = [
    "system_info", "open_app", "open_file", "close_app", "search_internet",
    "media_controls", "get_weather", "play_youtube", "play_spotify",
    "read_active_tab", "browser_navigate", "type_text"
]

# Keyword → additional tool names to include
_KEYWORD_ROUTES: list[tuple[re.Pattern, list[str]]] = [
    (re.compile(r"whatsapp|message|text|msg|send.*to", re.I),
     ["send_whatsapp", "send_whatsapp_file"]),

    (re.compile(r"file|read|write|document|pdf|pptx?|docx?|save|create.*file", re.I),
     ["read_file", "write_file", "find_file"]),

    (re.compile(r"screenshot|screen\s*shot|capture|snap", re.I),
     ["screenshot"]),

    (re.compile(r"volume|loud|quiet|mute|sound", re.I),
     ["set_volume"]),

    (re.compile(r"bright|dim|screen.*light", re.I),
     ["set_brightness"]),

    (re.compile(r"shutdown|restart|sleep|lock|power\s*(off|down)", re.I),
     ["system_control"]),

    (re.compile(r"remind|reminder|alarm|timer|notify.*later", re.I),
     ["set_reminder"]),

    (re.compile(r"type|write.*text|dictate|enter.*text", re.I),
     ["type_text"]),

    (re.compile(r"news|headline|latest", re.I),
     ["latest_news"]),

    (re.compile(r"design|webpage|web\s*page|html|tailwind|ui|landing\s*page|banao|likho|page", re.I),
     ["design_web_page", "write_file"]),

    (re.compile(r"navigate|click|button|ui\s*tree|focus", re.I),
     ["smart_navigate"]),

    (re.compile(r"fetch|http|api|url|download", re.I),
     ["http_get"]),

    (re.compile(r"chrome|browser|search.*in|read.*page|scroll|navigate|open.*url|click|score|ipl|cricbuzz|espncricinfo|cric", re.I),
     ["search_in_chrome", "browser_scroll", "browser_click", "get_page_elements"]),

    (re.compile(r"my\s*(name|info|preference|detail|fact)", re.I),
     ["get_user_info"]),
]


def get_tools_for_query(transcript: str) -> list[dict]:
    """
    Return only the tools relevant to this query.
    
    Core tools (~8) are always included.
    Extended tools are added only when transcript keywords match.
    
    Token savings: ~1,200–1,500 tokens per call for most queries.
    """
    # Start with core set
    selected_names = set(CORE_TOOLS)

    # Match keyword routes
    for pattern, tool_names in _KEYWORD_ROUTES:
        if pattern.search(transcript):
            selected_names.update(tool_names)

    # Build plugin tool dynamically
    tools = [_TOOL_INDEX[name] for name in selected_names if name in _TOOL_INDEX]
    
    plugin_tool = _build_plugin_tool()
    if plugin_tool:
        tools.append(plugin_tool)

    logger.debug(f"[TOOLS] Selected {len(tools)} tools for query (full set: {len(_ALL_TOOLS)})")
    return tools


def get_all_tools() -> list[dict]:
    """Return all tools (for backward compatibility or forced-full mode)."""
    tools = list(_ALL_TOOLS)
    plugin_tool = _build_plugin_tool()
    if plugin_tool:
        tools.append(plugin_tool)
    return tools


def _build_plugin_tool() -> dict | None:
    """Build the run_plugin tool schema with all registered plugin names."""
    try:
        from backend.plugins import get_all_plugins
        plugins = get_all_plugins()
        if not plugins:
            return None
        plugin_list = ", ".join(plugins.keys())
        return {
            "type": "function",
            "function": {
                "name": "run_plugin",
                "description": f"Execute plugin (available: {plugin_list}). Pass plugin_name and params.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "plugin_name": {"type": "string", "description": "Name of the plugin to execute"},
                    },
                    "required": ["plugin_name"],
                    "additionalProperties": False, # Strict for OpenAI 2.30.0
                },
            },
        }
    except Exception as e:
        logger.error(f"Failed to build plugin tool: {e}")
        return None
