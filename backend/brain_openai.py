"""
Yuki Brain v2 — GPT-4o-mini with OpenAI Function Calling.

Why function calling instead of JSON prompting:
  - Guaranteed structured output — no JSON parse errors, ever
  - Model picks the right function automatically (no prompt-tuning the action list)
  - No hallucinated clarification options
  - Naturally handles multi-turn conversation without special schema tricks
  - Faster: gpt-4o-mini avg ~600ms vs Gemma3:4b ~7s on CPU

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

# ── OpenAI Function Schemas ───────────────────────────────────────────────────
# The model picks which function to call (or none, for pure conversation).
# Guaranteed structured output — no regex, no JSON parse bugs.

_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "open_app",
            "description": "Open an application on the user's Windows PC.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "App name, e.g. 'chrome', 'spotify', 'whatsapp'"}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "close_app",
            "description": "Close a running application.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_whatsapp",
            "description": "Send a WhatsApp text message to a contact using the native WhatsApp Desktop app. Search by name — NEVER ask for phone number.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contact": {"type": "string", "description": "Contact name as it appears in WhatsApp, e.g. 'Shiv Bhaiya'"},
                    "message": {"type": "string", "description": "Message text to send"}
                },
                "required": ["contact", "message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_whatsapp_file",
            "description": "Send a file (document, ppt, pdf, image) via WhatsApp Desktop. Use this whenever user says 'send file', 'share document', 'send ppt', etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contact": {"type": "string", "description": "Contact name"},
                    "file_name": {"type": "string", "description": "Partial filename to search for, e.g. 'DATA MINING'"},
                    "file_path": {"type": "string", "description": "Full file path if known, otherwise leave empty"}
                },
                "required": ["contact", "file_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web for a query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_url",
            "description": "Open a specific URL in the browser.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "play_youtube",
            "description": "Search and play a video on YouTube.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "auto_play": {"type": "boolean", "default": True}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "play_spotify",
            "description": "Search and play a song or artist on Spotify.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string"}
                },
                "required": ["city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "system_info",
            "description": "Get system information like time, date, battery, CPU, or RAM.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "enum": ["time", "date", "battery", "cpu", "ram"]}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_volume",
            "description": "Set the system volume level (0-100).",
            "parameters": {
                "type": "object",
                "properties": {
                    "level": {"type": "integer", "minimum": 0, "maximum": 100}
                },
                "required": ["level"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_brightness",
            "description": "Set the screen brightness (0-100).",
            "parameters": {
                "type": "object",
                "properties": {
                    "level": {"type": "integer", "minimum": 0, "maximum": 100}
                },
                "required": ["level"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "screenshot",
            "description": "Take a screenshot of the current screen.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "reminder",
            "description": "Set a reminder for the user after a delay.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "What to remind the user about"},
                    "delay_minutes": {"type": "integer", "description": "Minutes from now"}
                },
                "required": ["text", "delay_minutes"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "clipboard_copy",
            "description": "Copy text to the system clipboard.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "file_op",
            "description": "Perform a file operation: copy, move, or delete.",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {"type": "string", "enum": ["copy", "move", "delete"]},
                    "source": {"type": "string"},
                    "dest": {"type": "string"}
                },
                "required": ["operation", "source"]
            }
        }
    },
]

# ── System prompt ─────────────────────────────────────────────────────────────

_SYSTEM = f"""You are {_ASSISTANT_NAME}, a female AI voice assistant on Windows 11.
You are helpful, witty, and speak like a real person — not a robot.
Keep responses SHORT (1-2 sentences) — this is voice output.

LANGUAGE RULES:
- If the user speaks Hindi or asks you to speak Hindi → respond in pure Hindi using DEVANAGARI script (हिंदी में लिखो, romanized mat karo).
- If the user speaks English or Hinglish → respond naturally in that style.
- You are FEMALE → use feminine Hindi grammar: "kar sakti hoon", "bolungi", "bhej diya".

BEHAVIOUR:
- If a function fits the request, call it. Don't ask unnecessary questions.
- For WhatsApp: NEVER ask for a phone number. The contact name is enough.
- If you genuinely don't understand, ask ONE short clarifying question.
- System context is provided per-turn: use it for time/date/battery answers.
"""

# ── Conversation history ──────────────────────────────────────────────────────

_history: list[dict] = []
_MAX_HISTORY = 12   # 6 turns


# ── Public API ────────────────────────────────────────────────────────────────

def is_available() -> bool:
    return bool(OPENAI_API_KEY)


def process(transcript: str) -> dict:
    """Send transcript to GPT-4o-mini, return brain-compatible result dict."""
    global _history

    if not OPENAI_API_KEY:
        return _error("OpenAI API key not set. Add OPENAI_API_KEY to .env")

    try:
        from openai import OpenAI
    except ImportError:
        return _error("openai package not installed. Run: pip install openai")

    client = OpenAI(api_key=OPENAI_API_KEY)

    # Build dynamic system context
    now      = datetime.datetime.now()
    context  = f"Time: {now.strftime('%I:%M %p')} | Date: {now.strftime('%A, %B %d %Y')}"
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

    messages = [{"role": "system", "content": system_content}, *_history]

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            tools=_TOOLS,
            tool_choice="auto",
            temperature=0.4,
            max_tokens=200,
        )

        msg = response.choices[0].message

        # ── Function call ─────────────────────────────────────────────────────
        if msg.tool_calls:
            tool_call = msg.tool_calls[0]
            fn_name   = tool_call.function.name
            fn_params = json.loads(tool_call.function.arguments)

            # Store assistant reply in history (with tool call)
            _history.append({"role": "assistant", "content": msg.content or "", "tool_calls": [
                {"id": tool_call.id, "type": "function", "function": {"name": fn_name, "arguments": tool_call.function.arguments}}
            ]})

            logger.info(f"Function call: {fn_name}({fn_params})")
            return {
                "needs_clarify": False,
                "action": {"type": fn_name, "params": fn_params},
                "response": None,
                "question": None,
                "options": [],
            }

        # ── Conversational reply ──────────────────────────────────────────────
        reply = (msg.content or "").strip()
        _history.append({"role": "assistant", "content": reply})
        logger.info(f"Conversational reply: {reply[:100]}")
        return {
            "needs_clarify": False,
            "action": {"type": "none", "params": {}},
            "response": reply,
            "question": None,
            "options": [],
        }

    except Exception as e:
        logger.error(f"OpenAI brain error: {e}")
        return _error(f"AI error: {str(e)[:80]}")


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
