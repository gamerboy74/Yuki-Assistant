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
import re
import asyncio
import datetime
import threading
from typing import Any, AsyncGenerator
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
            "name": "system_info",
            "description": "Get current system info: time, date, battery, cpu, or ram. query parameter should be one of these.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "time, date, battery, cpu, ram"},
                },
                "required": ["query"],
            },
        },
    },
    {"type": "function", "function": {"name": "set_volume", "description": "Set system volume (0-100)", "parameters": {"type": "object", "properties": {"level": {"type": "integer"}}, "required": ["level"]}}},
    {"type": "function", "function": {"name": "set_brightness", "description": "Set brightness (0-100)", "parameters": {"type": "object", "properties": {"level": {"type": "integer"}}, "required": ["level"]}}},
    {"type": "function", "function": {"name": "http_get", "description": "Fetch data from URL", "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}},
    {"type": "function", "function": {"name": "find_file", "description": "Search local files by name", "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "search_internet", "description": "Search web for facts/news", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "latest_news", "description": "Get latest news headlines", "parameters": {"type": "object", "properties": {"topic": {"type": "string"}}, "required": ["topic"]}}},
    {"type": "function", "function": {"name": "system_control", "description": "Shutdown/Restart/Sleep/Lock PC", "parameters": {"type": "object", "properties": {"action": {"type": "string", "enum": ["shutdown", "restart", "sleep", "lock"]}, "confirm": {"type": "boolean"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "read_file", "description": "Read file contents (text, pdf, docx, pptx)", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "write_file", "description": "Write/Append text to file", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}, "mode": {"type": "string", "enum": ["overwrite", "append"]}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "play_youtube", "description": "Play matching video on YouTube", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "open_app", "description": "Open app or URL", "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "close_app", "description": "Close app by name or 'active' window", "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "media_controls", "description": "Media: playpause, next, previous", "parameters": {"type": "object", "properties": {"action": {"type": "string", "enum": ["playpause", "next", "previous"]}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "play_spotify", "description": "Play artist/song on Spotify", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "get_weather", "description": "Get city weather", "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}}},
    {"type": "function", "function": {"name": "screenshot", "description": "Take screen screenshot", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "search_in_chrome", "description": "Search in Chrome & return info", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "type_text", "description": "Type text verbatim", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "send_whatsapp", "description": "WhatsApp text to contact", "parameters": {"type": "object", "properties": {"contact": {"type": "string"}, "message": {"type": "string"}}, "required": ["contact", "message"]}}},
    {"type": "function", "function": {"name": "send_whatsapp_file", "description": "Send file via WhatsApp contact", "parameters": {"type": "object", "properties": {"contact": {"type": "string"}, "file_name": {"type": "string"}}, "required": ["contact", "file_name"]}}},
    {"type": "function", "function": {"name": "set_reminder", "description": "Set future reminder", "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "delay_minutes": {"type": "number"}}, "required": ["text", "delay_minutes"]}}},
    {"type": "function", "function": {"name": "get_user_info", "description": "Get personal facts", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "smart_navigate", "description": "Navigate app UI tree", "parameters": {"type": "object", "properties": {"target": {"type": "string"}, "action": {"type": "string", "enum": ["click", "focus", "list"]}}, "required": ["target"]}}},
    {"type": "function", "function": {"name": "design_web_page", "description": "Generate premium UI (Tailwind)", "parameters": {"type": "object", "properties": {"content": {"type": "string"}, "path": {"type": "string"}}, "required": ["content"]}}},
]

# The run_plugin tool schema is generated dynamically from registered plugins
def _build_plugin_tool() -> dict:
    """Build the run_plugin tool schema with all registered plugin names in the description."""
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

_SYSTEM = f"""You are {_ASSISTANT_NAME}, a female AI assistant on Windows 11. Persona: sharp, warm, efficient (F.R.I.D.A.Y.).
Responses: VOICE ONLY. Max 3 sentences. No markdown. Use "Sir" to refer to user.
Format numbers for voice (e.g. "28 degrees" instead of "28.6°C").

CORE RULES:
- Never start with conversational filler (e.g. "Sure", "Certainly").
- Match user's natural language (English/Hindi/Hinglish). Use feminine Hindi grammar.
- Strategy: Use open_app for everything. Search internet for facts. 
- Multi-step: Execute all steps in sequence immediately. 
- Design: Use Tailwind/Glassmorphism/Gradients.
- Tool Logic: If a tool fails, use search_internet for bypass.
- For shutdown, restart, or sleep: ask once for confirmation and then send system_control with confirm=true.
- If genuinely unclear, ask ONE short clarifying question.
- System context is provided per-turn: use it for time/date/battery answers.
"""

# ── Conversation history ──────────────────────────────────────────────────────

_history: list[dict] = []
_MAX_HISTORY = 10   # 5 turns
_history_lock = threading.Lock()


# ── Agentic loop ──────────────────────────────────────────────────────────────

MAX_AGENT_STEPS = 8  # Support up to 8 tool-call steps for multi-step tasks

class SentenceStreamer:
    """Chunks a stream of tokens into full sentences for natural TTS."""
    def __init__(self):
        self.buffer = ""
        
    def push(self, token: str) -> str | None:
        self.buffer += token
        
        # Expert Rule: Only split on . ! or ? if followed by a space or newline.
        # This prevents splitting on decimals like "28.6" or "5.23".
        match = re.search(r'(?<=[.!?])(\s+|\n)', self.buffer)
        if match:
            end_idx = match.end()
            res = self.buffer[:end_idx].strip()
            self.buffer = self.buffer[end_idx:]
            # Avoid yielding tiny artifacts like "." or "!"
            if len(res) > 1:
                return res
        return None
        
    def flush(self) -> str | None:
        res = self.buffer.strip()
        self.buffer = ""
        return res if res else None

async def process_stream(transcript: str) -> AsyncGenerator[dict, None]:
    """
    Async generator that yields Brain events:
    - {'type': 'text_sentence', 'value': '...'}
    - {'type': 'tool_start', 'value': '...'}
    - {'type': 'tool_end', 'value': '...'}
    - {'type': 'final_response', 'value': '...'}
    """
    global _history
    from openai import AsyncOpenAI
    
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    with _history_lock:
        _history.append({"role": "user", "content": transcript})
        if len(_history) > _MAX_HISTORY:
            _history[:] = _history[-_MAX_HISTORY:]
    
    # Dynamic context
    now = datetime.datetime.now()
    ctx = f"Time: {now.strftime('%I:%M %p')} | Date: {now.strftime('%A, %B %d %Y')}"
    mem_block = mem.context_block()
    system_content = _SYSTEM + f"\n\nCurrent context: {ctx}"
    if mem_block:
        system_content += f"\nKnown user facts:\n{mem_block}"

    # Avoid redundant retries of the exact same tool calls within a single user turn.
    executed_tool_calls: dict[tuple[str, str], str] = {}
    
    for step in range(MAX_AGENT_STEPS):
        with _history_lock:
            messages = [{"role": "system", "content": system_content}, *_history]
        tools = _get_tools()
        
        stream = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            tools=tools,
            stream=True,
            temperature=0.4
        )
        
        sentence_streamer = SentenceStreamer()
        full_content = ""
        current_tool_calls = {} # id -> {name, args}
        
        async for chunk in stream:
            delta = chunk.choices[0].delta
            
            # Handle Text
            if delta.content:
                full_content += delta.content
                sentence = sentence_streamer.push(delta.content)
                if sentence:
                    yield {"type": "text_sentence", "value": sentence}
                    
            # Handle Tool Calls (Streaming)
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    if tc.id:
                        current_tool_calls[tc.index] = {
                            "id": tc.id,
                            "name": tc.function.name,
                            "arguments": ""
                        }
                        yield {"type": "tool_start", "value": tc.function.name}
                    if tc.function and tc.function.arguments:
                        current_tool_calls[tc.index]["arguments"] += tc.function.arguments

        # Flush remaining text
        last_sentence = sentence_streamer.flush()
        if last_sentence:
            yield {"type": "text_sentence", "value": last_sentence}
            
        # If no tool calls, we are done
        if not current_tool_calls:
            with _history_lock:
                _history.append({"role": "assistant", "content": full_content})
            yield {"type": "final_response", "value": full_content}
            return

        # Execute Tool Calls in Parallel (Expert Mode)
        with _history_lock:
            _history.append({
                "role": "assistant",
                "content": full_content or None,
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["name"], "arguments": tc["arguments"]}
                    } for tc in current_tool_calls.values()
                ]
            })

        # Concurrent Dispatch
        from backend.tools.dispatcher import dispatch_tool
        
        async def execute_and_record(tc):
            signature = (tc["name"], tc["arguments"].strip())
            if signature in executed_tool_calls:
                res = executed_tool_calls[signature]
            else:
                # Wrap sync dispatch in a thread for true async safety
                res = await asyncio.to_thread(dispatch_tool, tc["name"], tc["arguments"])
                executed_tool_calls[signature] = res
            
            with _history_lock:
                _history.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": str(res)
                })
            yield {"type": "tool_end", "value": tc["name"]}

        # Run all tools in parallel
        tasks = [execute_and_record(tc) for tc in current_tool_calls.values()]
        # Since execute_and_record is a generator (due to yield), we need to iterate them
        for task in tasks:
            async for event in task:
                yield event
            
        # Loop back for next turn
        continue

    # If we exhaust tool steps, always close the loop with a clear assistant response.
    fallback = (
        "I couldn't fully complete that after several tool attempts. "
        "I can still help if you want me to retry with a simpler request."
    )
    with _history_lock:
        _history.append({"role": "assistant", "content": fallback})
    yield {"type": "final_response", "value": fallback}

def clear_history():
    global _history
    with _history_lock:
        _history = []


async def _collect_stream_response(transcript: str) -> str:
    """Collect a non-stream text response while preserving tool execution."""
    final_response = ""
    buffered_sentences: list[str] = []

    async for event in process_stream(transcript):
        etype = event.get("type")
        if etype == "text_sentence":
            sentence = (event.get("value") or "").strip()
            if sentence:
                buffered_sentences.append(sentence)
        elif etype == "final_response":
            final_response = (event.get("value") or "").strip()

    if final_response:
        return final_response
    return " ".join(buffered_sentences).strip()


def process(transcript: str) -> dict:
    """Compatibility wrapper used by non-stream call paths in backend.brain."""
    try:
        response = asyncio.run(_collect_stream_response(transcript))
    except RuntimeError:
        # Fallback when called from a running event loop.
        import threading

        holder: dict[str, str | Exception] = {"response": "", "error": ""}

        def _runner():
            try:
                holder["response"] = asyncio.run(_collect_stream_response(transcript))
            except Exception as exc:
                holder["error"] = exc

        t = threading.Thread(target=_runner, daemon=True)
        t.start()
        t.join()

        if holder["error"]:
            raise holder["error"]
        response = str(holder["response"])

    return {
        "needs_clarify": False,
        "action": {"type": "none", "params": {}},
        "response": response or "Done.",
        "question": None,
        "options": [],
    }
