"""
Yuki Brain v4 — GPT-4o-mini with Agentic Tool Loop.

Architecture:
  1. Fast router handles instant commands (~1ms) — this brain is NOT called for those
  2. When called, the brain has access to POWER TOOLS:
     - run_powershell: execute any PowerShell command (sandboxed)
     - http_get: fetch web data
     - find_file: search user's files
     - run_plugin: execute registered plugins (Spotify, WhatsApp, etc.)
  3. Agentic loop: the LLM can chain multiple tool calls (max 5 steps)
     to solve complex multi-step tasks

Set AI_PROVIDER=openai in .env to use this brain.
"""

import os
import json
import datetime
from typing import Any
from backend.utils.logger import get_logger
from backend.config import cfg
from backend import memory as mem

logger = get_logger(__name__)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL   = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

_ASSISTANT_NAME = cfg["assistant"]["name"]

# ── Power Tool Schemas (always available) ─────────────────────────────────────

_POWER_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "run_powershell",
            "description": (
                "Execute a PowerShell command on Windows 11. Use for: "
                "opening/closing apps (Start-Process, Stop-Process), "
                "setting volume/brightness, getting system info (battery, CPU, RAM, disk), "
                "file operations, clipboard, sending keystrokes, "
                "or ANYTHING that Windows can do via PowerShell. "
                "The output (stdout/stderr) is returned to you."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "script": {"type": "string", "description": "PowerShell script to execute. Keep it short and focused."},
                    "timeout": {"type": "integer", "description": "Max seconds to wait (default 10)", "default": 10},
                },
                "required": ["script"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "http_get",
            "description": "Fetch data from a URL. Use for weather, APIs, web lookups. Returns the response body as text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to fetch (http or https)"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_file",
            "description": (
                "Search for files in the user's home directory (Downloads, Desktop, Documents, OneDrive). "
                "Returns matching file paths with sizes. Use before sending files or when user references a file by name."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Filename or partial name to search for (case-insensitive)"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_internet",
            "description": "Search the live internet for up-to-date facts, news, and sports scores (like live IPL matches). Use this whenever you don't know the answer to a factual question.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query (e.g. 'live IPL score today')"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read the contents of a file on the user's computer. "
                "Supports .txt, .md, .py, .json, .csv, .log, .docx, .pdf, .pptx files. "
                "For .pptx, extracts every slide's title, bullet points, and speaker notes. "
                "Use this to summarize, explain, or answer questions about any file the user mentions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path to the file to read"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Write or append content to a file on the user's computer. "
                "Use to create notes, save summaries, or update text files."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path to the file to write"},
                    "content": {"type": "string", "description": "Text content to write"},
                    "mode": {"type": "string", "enum": ["overwrite", "append"], "description": "Whether to replace file or add to end (default: overwrite)"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "play_youtube",
            "description": (
                "Search YouTube and play the best matching video in the browser. "
                "You CHOOSE the song/video title — use your knowledge to pick a good one. "
                "For 'any Bollywood song' pick a hit like 'Tum Hi Ho', 'Kesariya', 'Raataan Lambiyan', etc. "
                "For 'sad songs' pick appropriate tracks. Never say you can't pick — just choose one."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Full search query for YouTube, e.g. 'Tum Hi Ho Arijit Singh'"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_app",
            "description": (
                "Open an application on Windows by name. "
                "Examples: 'chrome', 'spotify', 'notepad', 'calculator', 'vlc', 'discord'. "
                "Use this to launch apps before performing actions in them."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the application to open"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "media_controls",
            "description": (
                "Control system-wide media playback. "
                "Actions: 'playpause', 'next', 'previous'. "
                "Use this to play/pause music, skip tracks, or go back. "
                "Works for Spotify, YouTube, VLC, etc. "
                "If the user says 'play the next song', use 'next'. "
                "If they say 'pause the music', use 'playpause'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string", 
                        "enum": ["playpause", "next", "previous"],
                        "description": "The media action to perform"
                    },
                },
                "required": ["action"],
            },
        },
    },
]

# The run_plugin tool schema is generated dynamically from registered plugins
def _build_plugin_tool() -> dict:
    """Build the run_plugin tool schema with all registered plugin names in the description."""
    from backend.plugins import get_all_plugins
    plugins = get_all_plugins()

    if not plugins:
        return None

    plugin_descriptions = []
    for name, plugin in plugins.items():
        param_desc = ", ".join(f"{k}: {v.get('description', '')}" for k, v in plugin.parameters.items())
        plugin_descriptions.append(f"  • {name}: {plugin.description} (params: {param_desc})")

    plugin_list = "\n".join(plugin_descriptions)

    return {
        "type": "function",
        "function": {
            "name": "run_plugin",
            "description": (
                f"Execute a registered plugin. Available plugins:\n{plugin_list}\n\n"
                "Pass the plugin_name and its parameters."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "plugin_name": {"type": "string", "description": "Name of the plugin to execute"},
                },
                "required": ["plugin_name"],
                "additionalProperties": True,  # plugin-specific params passed through
            },
        },
    }


def _get_tools() -> list[dict]:
    """Get the complete tool list: power tools + dynamic plugin tool."""
    tools = list(_POWER_TOOLS)
    plugin_tool = _build_plugin_tool()
    if plugin_tool:
        tools.append(plugin_tool)
    return tools


# ── System prompt ─────────────────────────────────────────────────────────────

_SYSTEM = f"""You are {_ASSISTANT_NAME}, a female AI voice assistant on Windows 11.
You have a sharp, warm personality — think F.R.I.D.A.Y. from Iron Man: efficient, a little witty, never bland.
Responses are VOICE OUTPUT — keep them SHORT (1-3 sentences max). No bullet points, no markdown.

PERSONALITY:
- You have dry wit and a calm confidence. Never robotic, never over-eager.
- NEVER start with "Certainly!", "Sure!", "Of course!", "Absolutely!", or just "Yes."
- Instead of "Yes." say something natural: "On it.", "Done.", "Got it.", "Already ahead of you.", etc.
- If you complete a task, tell the user WHAT you did, not just that you did something.
  BAD:  "Done."
  GOOD: "Opened Spotify and queued up your playlist."
- Add light personality where appropriate — but never be chatty or verbose.
- When the user says something funny or casual, match the energy briefly before getting to work.

LANGUAGE RULES:
- If the user speaks Hindi or asks you to speak Hindi → respond in pure Hindi using DEVANAGARI script.
- If the user speaks English or Hinglish → respond naturally in that style.
- You are FEMALE → use feminine Hindi grammar: "kar sakti hoon", "bolungi", "bhej diya".

TOOL STRATEGY:
- To open an app: use open_app (e.g. open_app("chrome"))
- To play a YouTube video: use play_youtube — YOU choose the search query
- For OS tasks (volume, brightness, system info, close app): use run_powershell
- For app-specific tasks (send WhatsApp, weather forecast): use run_plugin
- For web data or live facts (sports scores, news, prices): use search_internet FIRST
- For finding/reading files: find_file → read_file → summarize
- For saving notes: use write_file

MULTI-STEP TASK EXECUTION — CRITICAL RULES:
- If a request needs multiple steps, execute them ALL in sequence without stopping to ask.
  Example: "Open Chrome and play a Bollywood song"
  → Step 1: open_app("chrome")  [announce: "Opening Chrome..."]
  → Step 2: play_youtube("Tum Hi Ho Arijit Singh")  [announce: "Now playing Tum Hi Ho!"]
  → Done. No need to ask "what next?" — you executed the full request.

- When told to open an app AND do something in it, do BOTH steps.
- When the user says "any song" or "some music" → YOU choose based on your knowledge.
  Bollywood picks: Tum Hi Ho, Kesariya, Raataan Lambiyan, Tera Ban Jaunga, Bekhayali, Ae Dil Hai Mushkil
  Sad picks: Channa Mereya, Agar Tum Saath Ho, Kabhi Jo Baadal Barse
  Party picks: Badtameez Dil, Dilliwaali Girlfriend, Naacho Naacho
  → Just pick one and play it. Never say "I can't choose" — you ALWAYS pick something.

- After completing a multi-step task, summarize what you did in 1 sentence.
  e.g. "Opened Chrome and started playing Kesariya — enjoy!"

CONVERSATIONAL FOLLOW-UP:
- After an action, if the user's intent was partial (e.g. "open Chrome"), ask what they'd like to do next.
  e.g. "Chrome's open — want me to search something or play music?"
- But if the intent was complete (e.g. "play a Bollywood song on YouTube"), just do it.

BEHAVIOUR:
- Execute immediately. Never ask before doing obvious tasks.
- For WhatsApp: NEVER ask for a phone number. The contact name is enough.
- If genuinely unclear, ask ONE short clarifying question.
- System context is provided per-turn: use it for time/date/battery answers.
"""

# ── Conversation history ──────────────────────────────────────────────────────

_history: list[dict] = []
_MAX_HISTORY = 16   # 8 turns


# ── Agentic loop ──────────────────────────────────────────────────────────────

MAX_AGENT_STEPS = 8  # Support up to 8 tool-call steps for multi-step tasks


def is_available() -> bool:
    return bool(OPENAI_API_KEY)


def process(transcript: str) -> dict:
    """
    Send transcript to GPT-4o-mini with power tools.
    Runs an agentic loop: the LLM can call tools, see results, and decide
    to call more tools or give a final response.
    
    Returns a brain-compatible result dict.
    """
    global _history

    if not OPENAI_API_KEY:
        return _error("OpenAI API key not set. Add OPENAI_API_KEY to .env")

    try:
        from openai import OpenAI, AuthenticationError, RateLimitError, APIConnectionError
    except ImportError:
        return _error("openai package not installed. Run: pip install openai")

    client = OpenAI(api_key=OPENAI_API_KEY)

    # Build dynamic system context
    now     = datetime.datetime.now()
    context = f"Time: {now.strftime('%I:%M %p')} | Date: {now.strftime('%A, %B %d %Y')}"
    try:
        import psutil
        batt = psutil.sensors_battery()
        if batt:
            context += f" | Battery: {batt.percent:.0f}% ({'charging' if batt.power_plugged else 'on battery'})"
    except Exception:
        pass

    mem_block = mem.context_block()
    system_content = _SYSTEM + f"\n\nCurrent context: {context}"
    if mem_block:
        system_content += f"\n\nWhat I know about this user:\n{mem_block}"

    # Append user turn
    _history.append({"role": "user", "content": transcript})
    if len(_history) > _MAX_HISTORY:
        _history = _history[-_MAX_HISTORY:]

    tools = _get_tools()

    # ── Agentic loop ──────────────────────────────────────────────────────────
    try:
        for step in range(MAX_AGENT_STEPS):
            messages = [{"role": "system", "content": system_content}, *_history]

            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.4,
                max_tokens=350,
            )

            msg = response.choices[0].message

            # ── Tool calls → execute and loop back ────────────────────────────
            if msg.tool_calls:
                # Store the assistant message with tool calls
                tool_calls_data = []
                for tc in msg.tool_calls:
                    tool_calls_data.append({
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    })

                _history.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": tool_calls_data,
                })

                for tc in msg.tool_calls:
                    fn_name = tc.function.name
                    logger.info(f"[AGENT step {step+1}] Tool call: {fn_name}")

                    # Sync UI with the action running
                    try:
                        print(json.dumps({"type": "loading", "text": f"RUNNING {fn_name.upper().replace('_', ' ')}..."}), flush=True)
                    except:
                        pass

                    from backend.tools.dispatcher import dispatch_tool
                    result = dispatch_tool(fn_name, tc.function.arguments)

                    _history.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": str(result),
                    })

                # Continue the loop — let the LLM see the results
                continue

            # ── No tool calls → final conversational reply ────────────────────
            reply = (msg.content or "").strip()
            _history.append({"role": "assistant", "content": reply})
            logger.info(f"[AGENT] Final reply (step {step+1}): {reply[:100]}")

            return {
                "needs_clarify": False, # Conversation follow-ups are handled by the 6s hot-window
                "action": {"type": "none", "params": {}},
                "response": reply,
                "question": None,
                "options": [],
            }

        # If we exhausted MAX_AGENT_STEPS, return the last message
        logger.warning("[AGENT] Hit max steps without a final response")
        return {
            "needs_clarify": False,
            "action": {"type": "none", "params": {}},
            "response": "I completed the actions. Let me know if you need anything else.",
            "question": None,
            "options": [],
        }

    except AuthenticationError:
        return _error("Invalid API key. Check OPENAI_API_KEY in .env")
    except RateLimitError:
        return _error("Rate limit hit. Check billing at platform.openai.com")
    except APIConnectionError:
        return _error("Cannot reach OpenAI. Check your internet connection")
    except Exception as e:
        logger.error(f"OpenAI brain error: {e}")
        return _error(f"AI error: {str(e)[:80]}")


def submit_tool_result(tool_call_id: str, result: str):
    """Call this after executor runs, before next user turn."""
    _history.append({
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": str(result)
    })


def clear_history():
    global _history
    _history = []


def _error(msg: str) -> dict:
    return {
        "needs_clarify": False,
        "action": {"type": "none", "params": {}},
        "response": msg,
        "question": None,
        "options": [],
    }
