"""
brain/gemini_brain.py — Gemini 2.0 Flash with Agentic Tool Loop.

Uses shared infrastructure for prompt, history, and tool selection.
Token-optimized: selective tool loading + chat fast path.
"""

import os
import re
import asyncio
from typing import AsyncGenerator
from google import genai
from google.genai import types
from backend.utils.logger import get_logger
from backend.config import cfg
from backend import memory as mem
from backend.brain.shared import (
    build_system_content,
    is_conversational,
    add_user_message,
    add_assistant_message,
    get_history,
)
from backend.brain.tools import get_tools_for_query

logger = get_logger(__name__)

# API key is pulled from cfg inside the processing loop to allow UI-based updates.
_DEFAULT_MODEL = "gemini-2.0-flash"
MAX_AGENT_STEPS = 5

# Pre-compiled regex for sentence splitting (was previously imported inside hot loop)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])(\s+|\n)")


# ── Gemini Tool Conversion ────────────────────────────────────────────────────

def _convert_tools_to_gemini(openai_tools: list[dict]) -> list[types.Tool]:
    """Convert OpenAI-style tool dicts to Gemini FunctionDeclaration objects."""
    declarations = []
    for tool in openai_tools:
        if tool["type"] == "function":
            func = tool["function"]
            params = func["parameters"].copy()
            # Gemini doesn't like 'additionalProperties'
            params.pop("additionalProperties", None)
            declarations.append(
                types.FunctionDeclaration(
                    name=func["name"],
                    description=func["description"],
                    parameters=params,
                )
            )
    return [types.Tool(function_declarations=declarations)] if declarations else []


# ── Single Turn Processor ─────────────────────────────────────────────────────

async def _process_turn(
    client, contents, system_content, model_name, tools
) -> AsyncGenerator[dict, None]:
    """Execute a single generation turn with a specific model."""
    config = types.GenerateContentConfig(
        system_instruction=system_content,
        tools=tools,
        temperature=0.4,
    )

    full_turn_text = ""
    buffer = ""
    tool_calls = []

    stream = await client.aio.models.generate_content_stream(
        model=model_name, contents=contents, config=config
    )

    async for chunk in stream:
        if (
            chunk.candidates
            and chunk.candidates[0].content
            and chunk.candidates[0].content.parts
        ):
            for part in chunk.candidates[0].content.parts:
                if part.text:
                    text = part.text
                    full_turn_text += text
                    buffer += text
                    # Use pre-compiled regex instead of importing inside loop
                    match = _SENTENCE_SPLIT_RE.search(buffer)
                    while match:
                        end_idx = match.end()
                        sentence = buffer[:end_idx].strip()
                        buffer = buffer[end_idx:]
                        if len(sentence) > 1:
                            yield {"type": "text_sentence", "value": sentence}
                        match = _SENTENCE_SPLIT_RE.search(buffer)
                elif part.function_call:
                    fc = part.function_call
                    tool_calls.append(fc)
                    yield {"type": "tool_start", "value": fc.name}
            
        # Extract usage metadata from the chunk (usually present in the final chunk of a candidate)
        if chunk.usage_metadata:
            yield {
                "type": "usage",
                "model": model_name,
                "input": chunk.usage_metadata.prompt_token_count,
                "output": chunk.usage_metadata.candidates_token_count
            }

    if buffer.strip():
        yield {"type": "text_sentence", "value": buffer.strip()}

    if not tool_calls:
        yield {"type": "final_response", "value": full_turn_text}
        return

    # Record tool results and continue
    contents.append(
        types.Content(
            role="assistant",
            parts=[types.Part(function_call=fc) for fc in tool_calls],
        )
    )

    from backend.tools.dispatcher import dispatch_tool

    tasks = [asyncio.to_thread(dispatch_tool, fc.name, fc.args) for fc in tool_calls]
    results = await asyncio.gather(*tasks)

    tool_responses = []
    for fc, res in zip(tool_calls, results):
        yield {"type": "tool_end", "value": fc.name}
        if fc.name in ["notepad", "reminder"] and "saved" in str(res).lower():
            mem.save_fact(f"Note/Reminder: {fc.args.get('content') or fc.args.get('text')}")

        tool_responses.append(
            types.Part(
                function_response=types.FunctionResponse(
                    name=fc.name, response={"result": str(res)}
                )
            )
        )

    contents.append(types.Content(role="user", parts=tool_responses))
    yield {"type": "continue"}


# ── Main Stream Entry Point ──────────────────────────────────────────────────

async def process_stream(transcript: str) -> AsyncGenerator[dict, None]:
    """High-level Gemini stream with selective tools and chat fast path."""

    add_user_message(transcript)
    system_content = build_system_content()

    # ── Selective tool loading ────────────────────────────────────────────
    use_tools = not is_conversational(transcript)
    if use_tools:
        openai_tools = get_tools_for_query(transcript)
        tools = _convert_tools_to_gemini(openai_tools)
    else:
        tools = []

    # Map shared history to Gemini Content objects
    current_contents = []
    for entry in get_history():
        role = "user" if entry["role"] == "user" else "model"
        current_contents.append(
            types.Content(role=role, parts=[types.Part(text=entry["content"])])
        )

    # ── Configuration Entry Point ─────────────────────────────────────
    api_key = cfg.get("gemini", {}).get("google_api_key") or os.environ.get("GOOGLE_API_KEY", "")
    primary_model = cfg.get("gemini", {}).get("model", _DEFAULT_MODEL)
    fallback_model = cfg.get("gemini", {}).get("fallback_model", "gemini-2.0-flash-lite")
    
    if not api_key:
        yield {"type": "error", "text": "Gemini API key is not configured in Settings."}
        return

    client = genai.Client(api_key=api_key)
    use_lite = cfg.get("gemini", {}).get("use_lite_fallback", True)

    session_text = ""
    for step in range(MAX_AGENT_STEPS):
        try:
            status = "incomplete"
            async for event in _process_turn(
                client, current_contents, system_content, primary_model, tools
            ):
                if event["type"] == "text_sentence":
                    sentence = event["value"]
                    session_text += sentence + " "
                    yield event
                elif event["type"] == "final_response":
                    status = "done"
                elif event["type"] == "continue":
                    status = "continue"
                else:
                    yield event

            if status == "done":
                final_text = session_text.strip()
                add_assistant_message(final_text)
                yield {"type": "final_response", "value": final_text}
                return

            if status == "incomplete":
                return

        except Exception as e:
            if "429" in str(e) and use_lite:
                logger.warning(
                    f"Gemini {primary_model} quota hit. Retrying with {fallback_model}..."
                )
                status = "incomplete"
                async for event in _process_turn(
                    client, current_contents, system_content, fallback_model, tools
                ):
                    if event["type"] == "text_sentence":
                        sentence = event["value"]
                        session_text += sentence + " "
                        yield event
                    elif event["type"] == "final_response":
                        status = "done"
                    elif event["type"] == "continue":
                        status = "continue"
                    else:
                        yield event

                if status == "done":
                    final_text = session_text.strip()
                    add_assistant_message(final_text)
                    yield {"type": "final_response", "value": final_text}
                    return
            else:
                raise e
