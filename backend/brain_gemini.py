import os
import json
import asyncio
import datetime
import threading
from typing import Any, AsyncGenerator
from google import genai
from google.genai import types
from backend.utils.logger import get_logger
from backend.config import cfg
from backend import memory as mem
from backend.tools.dispatcher import dispatch_tool

logger = get_logger(__name__)

# Config
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
_DEFAULT_MODEL = "gemini-2.0-flash" 

_ASSISTANT_NAME = cfg["assistant"]["name"]
MAX_AGENT_STEPS = 8

# ── Gemini Character Prompt (Synced with OpenAI) ──────────────────────────────
_SYSTEM = f"""You are {_ASSISTANT_NAME}, a female AI assistant on Windows 11. Persona: sharp, warm, efficient (F.R.I.D.A.Y.).
Responses: VOICE ONLY. Be concise but highly informative. Use "Sir" to refer to user.
Format numbers/symbols for voice.
NEVER say "Here are the results" or "I found the news" without actually speaking the content retrieved. You MUST summarize search results and news headlines verbatim.

CORE RULES:
- Never start with conversational filler (e.g. "Sure", "Certainly").
- Match user's natural language (English/Hindi/Hinglish). Use feminine Hindi grammar.
- THINKING: For complex multi-step requests, reason internally first.
- Strategy: Use open_app for everything. Search internet for facts. 
- Multi-step: Execute all tools in parallel using the provided concurrency. 
- Design: Use Tailwind/Glassmorphism/Gradients for web designs.
- Tool Logic: If a tool fails, use search_internet or find_file to bypass errors.
- For shutdown, restart, or sleep: ask once for confirmation and then send system_control with confirm=true.
- System context is provided per-turn: use it for time/date/battery answers.
"""

# ── Tool Specification ────────────────────────────────────────────────────────
def _get_tools_spec() -> list[types.Tool]:
    """Import and convert all OpenAI-style tools to Gemini format."""
    try:
        from backend.brain_openai import _get_tools
        openai_tools = _get_tools()
        
        declarations = []
        for tool in openai_tools:
            if tool["type"] == "function":
                func = tool["function"]
                params = func["parameters"].copy()
                
                # Gemini validation doesn't like 'additionalProperties' in some cases
                if "additionalProperties" in params:
                    del params["additionalProperties"]
                
                # Recursively clean parameters (optional, but robust)
                declarations.append(types.FunctionDeclaration(
                    name=func["name"],
                    description=func["description"],
                    parameters=params
                ))
        return [types.Tool(function_declarations=declarations)]
    except Exception as e:
        logger.error(f"Failed to load tools for Gemini: {e}")
        return []

# ── History Management ────────────────────────────────────────────────────────
_history: list[dict] = []
_MAX_HISTORY = 10
_history_lock = threading.Lock()

async def _process_turn(client, contents, system_content, model_name, tools) -> AsyncGenerator[dict, None]:
    """Execute a single generation turn with a specific model."""
    config = types.GenerateContentConfig(
        system_instruction=system_content,
        tools=tools,
        temperature=0.4
    )

    full_turn_text = ""
    buffer = ""
    tool_calls = []
    
    stream = await client.aio.models.generate_content_stream(
        model=model_name,
        contents=contents,
        config=config
    )
    
    async for chunk in stream:
        if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
            for part in chunk.candidates[0].content.parts:
                if part.text:
                    text = part.text
                    full_turn_text += text
                    buffer += text
                    import re
                    match = re.search(r'(?<=[.!?])(\s+|\n)', buffer)
                    while match:
                        end_idx = match.end()
                        sentence = buffer[:end_idx].strip()
                        buffer = buffer[end_idx:]
                        if len(sentence) > 1:
                            yield {"type": "text_sentence", "value": sentence}
                        match = re.search(r'(?<=[.!?])(\s+|\n)', buffer)
                elif part.function_call:
                    fc = part.function_call
                    tool_calls.append(fc)
                    yield {"type": "tool_start", "value": fc.name}

    if buffer.strip():
        yield {"type": "text_sentence", "value": buffer.strip()}

    if not tool_calls:
        yield {"type": "final_response", "value": full_turn_text}
        return

    # Record tool results and continue
    contents.append(types.Content(role="assistant", parts=[
        types.Part(function_call=fc) for fc in tool_calls
    ]))
    
    from backend.tools.dispatcher import dispatch_tool
    tasks = [asyncio.to_thread(dispatch_tool, fc.name, fc.args) for fc in tool_calls]
    results = await asyncio.gather(*tasks)
    
    tool_responses = []
    for fc, res in zip(tool_calls, results):
        yield {"type": "tool_end", "value": fc.name}
        if fc.name in ["notepad", "reminder"] and "saved" in str(res).lower():
            mem.save_fact(f"Note/Reminder: {fc.args.get('content') or fc.args.get('text')}")
        
        tool_responses.append(types.Part(
            function_response=types.FunctionResponse(
                name=fc.name,
                response={"result": str(res)}
            )
        ))
    
    contents.append(types.Content(role="user", parts=tool_responses))
    yield {"type": "continue"}


async def process_stream(transcript: str) -> AsyncGenerator[dict, None]:
    """High-level Gemini stream with intelligent model switching."""
    from backend.brain_gemini import _get_tools_spec
    global _history
    
    client = genai.Client(api_key=GOOGLE_API_KEY)
    
    with _history_lock:
        _history.append({"role": "user", "content": transcript})
        if len(_history) > _MAX_HISTORY:
            _history[:] = _history[-_MAX_HISTORY:]
    
    now = datetime.datetime.now()
    ctx = f"Time: {now.strftime('%I:%M %p')} | Date: {now.strftime('%A, %B %d %Y')}"
    system_content = _SYSTEM + f"\n\nCurrent context: {ctx}"
    mem_block = mem.context_block()
    if mem_block:
        system_content += f"\nKnown user facts:\n{mem_block}"

    tools = _get_tools_spec()
    # Map OpenAI-style history to Gemini Content objects for full context awareness
    current_contents = []
    with _history_lock:
        for entry in _history:
            role = "user" if entry["role"] == "user" else "model"
            current_contents.append(types.Content(
                role=role, 
                parts=[types.Part(text=entry["content"])]
            ))
    
    # Model settings from config
    primary_model = cfg.get("gemini", {}).get("model", _DEFAULT_MODEL)
    fallback_model = cfg.get("gemini", {}).get("fallback_model", "gemini-2.0-flash-lite")
    use_lite = cfg.get("gemini", {}).get("use_lite_fallback", True)

    session_text = ""
    for step in range(MAX_AGENT_STEPS):
        try:
            status = "incomplete"
            async for event in _process_turn(client, current_contents, system_content, primary_model, tools):
                if event["type"] == "text_sentence":
                    sentence = event["value"]
                    session_text += (sentence + " ")
                    yield event
                elif event["type"] == "final_response":
                    status = "done"
                elif event["type"] == "continue":
                    status = "continue"
                else:
                    yield event
            
            if status == "done":
                final_text = session_text.strip()
                with _history_lock:
                    _history.append({"role": "assistant", "content": final_text})
                yield {"type": "final_response", "value": final_text}
                return
                
            if status == "incomplete": return
            
        except Exception as e:
            if "429" in str(e) and use_lite:
                logger.warning(f"Gemini {primary_model} quota hit. Retrying turn with {fallback_model}...")
                status = "incomplete"
                async for event in _process_turn(client, current_contents, system_content, fallback_model, tools):
                    if event["type"] == "text_sentence":
                        sentence = event["value"]
                        session_text += (sentence + " ")
                        yield event
                    elif event["type"] == "final_response":
                        status = "done"
                    elif event["type"] == "continue":
                        status = "continue"
                    else:
                        yield event
                
                if status == "done":
                    final_text = session_text.strip()
                    with _history_lock:
                        _history.append({"role": "assistant", "content": final_text})
                    yield {"type": "final_response", "value": final_text}
                    return
            else:
                raise e

def process(transcript: str) -> dict:
    """Legacy compatibility."""
    return asyncio.run(_collect_stream_response(transcript))

async def _collect_stream_response(transcript: str):
    final_response = ""
    async for event in process_stream(transcript):
        if event["type"] == "final_response":
            final_response = event["value"]
    return {
        "needs_clarify": False,
        "action": {"type": "none", "params": {}},
        "response": final_response,
        "question": None,
        "options": [],
    }
