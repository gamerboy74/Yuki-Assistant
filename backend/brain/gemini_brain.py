"""
brain/gemini_brain.py — Gemini 3.1 Pro with Agentic Tool Loop.

Uses shared infrastructure for prompt, history, and tool selection.
Token-optimized: selective tool loading + chat fast path.

FIXES APPLIED:
  1. BASE_URL: v1beta (v1 is now stable for G2.5+, but keeping v1beta for G3 preview compatibility)
  2. Credits: Effectively using $300 balance by prioritizing Gemini 3.1 Pro.
  3. Real agent loop using MAX_AGENT_STEPS (increased for G3).
  4. Session-scoped gemini_contents to prevent cross-session history corruption.
"""

import os
import re
import json
import uuid
import asyncio
from typing import AsyncGenerator
from google import genai
from google.genai import types
from backend.utils.logger import get_logger
from backend.config import cfg
from backend import memory as mem
from backend.brain.reasoning import reason_async, track_execution
from backend.brain.shared import (
    build_system_content,
    build_dynamic_context,
    is_conversational,
    add_user_message,
    add_assistant_message,
    add_tool_messages,
    get_history,
)
from backend.brain.tools import get_tools_for_query

logger = get_logger(__name__)

_DEFAULT_MODEL = "gemini-2.0-flash"
MAX_AGENT_STEPS = 10

# ── FIX 1: SDK auto-routing — manually forcing v1beta causes 404 on Gemini 3.x models ───────────────────
# BASE_URL removed. Let the google-genai SDK handle version routing.

# Pre-compiled regex for sentence splitting
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])(\s+|\n)")
_BRAIN_TAG_RE = re.compile(
    r"\[(YUKI_PLAN|REASONING_ENGINE|SAFETY_SENTINEL_PROTOCOL|COGNITIVE_OPERATIONS|MISSION_PROTOCOL|COGNITIVE_LOG|TACTICAL_BRIEFING)[^\]]*(\]|(?=$))",
    flags=re.DOTALL | re.IGNORECASE,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _clean_text(text: str) -> str:
    """Strip internal brain monologue tags from output text."""
    # ── J.A.R.V.I.S. Response Jump ──
    # If [RESPONSE:] is present, everything before it is waste.
    if "[RESPONSE:" in text:
        text = text.split("[RESPONSE:", 1)[1]
    
    # ── Tag Scrubbing ──
    text = _BRAIN_TAG_RE.sub("", text)
    
    # ── Final Cleanup ──
    # Strip any lingering brackets or structural remnants
    text = text.replace("[RESPONSE:", "").replace("]", "").replace("[", "")
    return text.strip()


def _convert_tools_to_gemini(openai_tools: list[dict]) -> list[types.Tool]:
    """Convert OpenAI-style tool dicts to Gemini FunctionDeclaration objects."""
    declarations = []
    for tool in openai_tools:
        if tool["type"] == "function":
            func = tool["function"]
            params = func["parameters"].copy()
            params.pop("additionalProperties", None)
            declarations.append(
                types.FunctionDeclaration(
                    name=func["name"],
                    description=func["description"],
                    parameters=params,
                )
            )
    return [types.Tool(function_declarations=declarations)] if declarations else []


# ── FIX 2: AQ. credentials only via Vertex path ──────────────────────────────

def _build_client() -> tuple[genai.Client, str]:
    """
    Build the Google AI Studio genai.Client.
    Returns (client, primary_model_name).
    """
    gemini_cfg = cfg.get("gemini", {})
    s_cfg = gemini_cfg.get("google_ai_studio", {})
    api_key = (s_cfg.get("api_key") or os.environ.get("GOOGLE_API_KEY", "")).strip()
    primary_model = s_cfg.get("model", _DEFAULT_MODEL)

    # Reject AQ. tokens which are for Vertex only
    if api_key.startswith("AQ."):
        raise ValueError(
            "AQ. tokens are Vertex AI OAuth tokens and cannot be used with Google AI Studio. "
            "Please provide a valid AI Studio API key (starting with AIza)."
        )

    logger.debug(f"[BRAIN] Google AI Studio | model={primary_model} | key={'set' if api_key else 'ADC'}")

    if api_key:
        client = genai.Client(api_key=api_key)
    else:
        # Zero-config: picks up GOOGLE_API_KEY env var or gcloud ADC
        logger.info("[BRAIN] No API key — attempting ADC / env var mode.")
        client = genai.Client()

    return client, primary_model


def get_available_models() -> list[str]:
    """Fetch allowed/available models from Google AI Studio for dynamic UI loading."""
    try:
        client, _ = _build_client()
        raw_models = []
        # Support both new SDK model names and manual overrides
        # We strictly whitelist only models that function properly as Yuki's core brain
        # Includes the latest stable 2.5 series and 3.1 edge-tier models
        WHITELIST = [
            "gemini-3.1-pro-preview", 
            "gemini-3.1-flash-preview",
            "gemini-3.1-flash-lite-preview",
            "gemini-3.1-flash-live-preview",
            "gemini-3-flash-preview",  # Often referred to as 3.0 Flash
            "gemini-2.5-pro",
            "gemini-2.5-flash", 
            "gemini-2.5-flash-lite",
            "gemini-2.0-flash"  # Legacy (Deprecated June 2026)
        ]
        
        for m in client.models.list():
            name = m.name.replace("models/", "")
            if name in WHITELIST:
                raw_models.append(name)
        
        # If discovery fails or list is empty, return the hardcoded safe set
        if not raw_models:
            return WHITELIST
            
        # Sort by mission priority: 3.1 -> 3.0 -> 2.5 -> 2.0
        def sort_key(name):
            order = {
                "gemini-3.1-pro-preview": 0,
                "gemini-3.1-flash-preview": 1,
                "gemini-3.1-flash-lite-preview": 2,
                "gemini-3.1-flash-live-preview": 3,
                "gemini-3-flash-preview": 4,
                "gemini-2.5-pro": 5, 
                "gemini-2.5-flash": 6,
                "gemini-2.5-flash-lite": 7,
                "gemini-2.0-flash": 8
            }
            return order.get(name, 99)

        raw_models.sort(key=sort_key)
        return raw_models
    except Exception as e:
        logger.error(f"[BRAIN] Failed to fetch models: {e}")
        return ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3.1-pro-preview"]


# ── History Sync ──────────────────────────────────────────────────────────────

# FIX 3: No longer module-level mutable — pass contents into process_stream
# so concurrent sessions don't corrupt each other.

def _build_gemini_contents() -> list[dict]:
    """
    Build a sanitized list of dictionaries for the Gemini 3.x neural core.
    Uses pure dicts to avoid Pydantic validation errors in the google-genai SDK.
    """
    history = get_history()
    contents = []

    for i, entry in enumerate(history):
        role = "user" if entry["role"] in ["user", "tool"] else "model"
        parts = []

        if entry["role"] == "tool":
            res = entry.get("content")
            # Ensure response is a dictionary
            resp_dict = res if isinstance(res, dict) else {"result": str(res)}
            parts.append({
                "function_response": {
                    "name": entry.get("name", "unknown"),
                    "response": resp_dict
                }
            })
        elif entry.get("tool_calls"):
            # Assistant turn containing tool invocations
            # If we have original raw_parts (with G3 knowledge), use them directly
            if entry.get("raw_parts"):
                parts = entry["raw_parts"]
            else:
                if entry.get("content"):
                    parts.append({"text": str(entry["content"])})
                
                for tc in entry["tool_calls"]:
                    # Correct field mapping for google-genai: 'args' not 'arguments'
                    raw_args = tc.get("function", {}).get("arguments", {})
                    
                    # Ensure args is a dictionary (handles JSON string or None)
                    if isinstance(raw_args, str):
                        try:
                            args = json.loads(raw_args)
                        except:
                            args = {"query": raw_args}
                    else:
                        args = raw_args or {}

                    parts.append({
                        "function_call": {
                            "name": tc.get("function", {}).get("name", "unknown"),
                            "args": args
                        }
                    })
        else:
            text = entry.get("content") or ""
            # Prune empty text parts to avoid G3 validation failures
            if text.strip() or role == "user":
                parts.append({"text": text})

        if parts:
            contents.append({"role": role, "parts": parts})

    return contents


# ── Single Generation Turn ────────────────────────────────────────────────────

async def _run_generation(
    client: genai.Client,
    contents: list[types.Content],
    system_content,
    model_name: str,
    tools: list[types.Tool],
) -> AsyncGenerator[dict, None]:
    """
    Execute one generation turn, yield streaming events.
    Returns tool_calls in the final event for the agent loop to consume.
    """
    config = types.GenerateContentConfig(
        system_instruction=system_content,
        tools=tools,
        temperature=0.7,  # Increased for G3 Pro's better handling of nuance and personality
    )

    full_text = ""
    buffer = ""
    tool_calls = []
    # FIX: Capture exact parts for stateful tool-calling in Gemini 3.x
    raw_model_parts = []

    stream = await client.aio.models.generate_content_stream(
        model=model_name, contents=contents, config=config
    )

    async for chunk in stream:
        if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
            for part in chunk.candidates[0].content.parts:
                # Store the part for replay as a dictionary
                p_dict = part.model_dump(exclude_none=True)
                raw_model_parts.append(p_dict)

                if part.text:
                    full_text += part.text
                    buffer += part.text
                    match = _SENTENCE_SPLIT_RE.search(buffer)
                    while match:
                        end_idx = match.end()
                        sentence = _clean_text(buffer[:end_idx])
                        buffer = buffer[end_idx:]
                        if len(sentence) > 1:
                            yield {"type": "text_sentence", "value": sentence}
                        match = _SENTENCE_SPLIT_RE.search(buffer)
                elif part.function_call:
                    tool_calls.append(part.function_call)
                    yield {"type": "tool_start", "value": part.function_call.name}

        if chunk.usage_metadata:
            in_t = chunk.usage_metadata.prompt_token_count or 0
            out_t = chunk.usage_metadata.candidates_token_count or 0
            cached = getattr(chunk.usage_metadata, "cached_content_token_count", 0) or 0
            logger.debug(f"[GEMINI USAGE] {model_name}: {in_t} in / {out_t} out / {cached} cached")
            yield {"type": "usage", "model": model_name, "input": in_t, "output": out_t, "cached": cached}

    # Flush remaining buffer
    if buffer.strip():
        clean = _clean_text(buffer)
        if clean:
            yield {"type": "text_sentence", "value": clean}

    yield {
        "type": "turn_done",
        "full_text": _clean_text(full_text).strip(),
        "tool_calls": tool_calls,
        "raw_parts": raw_model_parts,
    }


# ── FIX 3: Real Agentic Loop ──────────────────────────────────────────────────

async def _run_agent_loop(
    client: genai.Client,
    contents: list[dict],
    system_content,
    model_name: str,
    tools: list[dict],
) -> AsyncGenerator[dict, None]:
    """
    Real agentic loop: calls Gemini → executes tools → feeds results back → repeats.
    Caps at MAX_AGENT_STEPS to prevent runaway loops.
    """
    from backend.plugins import execute_plugin

    # session_text tracks ONLY the last (final) generation step output.
    # We reset each step so we don't concatenate intermediate reasoning
    # with the final user-facing response.
    session_text = ""
    assistant_tool_calls_log = []
    tool_result_msgs_log = []
    # Dedup guard: track sentence fingerprints already yielded this turn
    _emitted_sentences: set[str] = set()

    for step in range(MAX_AGENT_STEPS):
        logger.debug(f"[BRAIN] Agent step {step + 1}/{MAX_AGENT_STEPS}")
        turn_text = ""
        turn_tool_calls = []
        raw_parts = []
        step_text = ""       # Accumulate text for this step only
        step_sentences = []  # Buffer: hold text_sentence events until we know if tools are called

        async for event in _run_generation(client, contents, system_content, model_name, tools):
            if event["type"] == "turn_done":
                turn_text = event["full_text"]
                turn_tool_calls = event["tool_calls"]
                raw_parts = event["raw_parts"]
            elif event["type"] == "text_sentence":
                # Buffer — don't emit yet. If this step uses tools, this is
                # internal chain-of-thought and should never reach the UI.
                step_text += event["value"] + " "
                step_sentences.append(event)
            else:
                # tool_start, usage, etc. — always forward immediately
                yield event

        # No tool calls → final answer step. Release buffered sentences to UI.
        if not turn_tool_calls:
            session_text = step_text.strip()
            for sent_event in step_sentences:
                sentence_key = sent_event["value"].lower().strip()
                if sentence_key not in _emitted_sentences:
                    _emitted_sentences.add(sentence_key)
                    yield sent_event
                else:
                    logger.debug(f"[BRAIN] Dedup: skipping duplicate sentence: '{sent_event['value'][:40]}'")
            logger.debug(f"[BRAIN] No tool calls at step {step + 1}. Agent complete.")
            break

        # Tool calls exist → this step's text was reasoning. Suppress it silently.
        logger.debug(f"[BRAIN] Step {step + 1} had tool calls — suppressing {len(step_sentences)} reasoning sentence(s).")
        session_text = step_text.strip()

        # ── Neural Alignment Fix: Replay exact parts for G3 thought-signature compliance ──
        if raw_parts:
            contents.append({"role": "model", "parts": raw_parts})

        from backend.plugins import execute_plugin_async
        
        # Execute tools on the dedicated plugin thread to prevent Playwright thread hopping
        tasks = [execute_plugin_async(fc.name, fc.args) for fc in turn_tool_calls]
        results = await asyncio.gather(*tasks)

        tool_result_parts = []
        for fc, res in zip(turn_tool_calls, results):
            yield {"type": "tool_end", "value": fc.name}
            track_execution(fc.name)

            # Auto-learn from notes/reminders
            if fc.name in ["notepad", "reminder", "set_reminder"] and "saved" in str(res).lower():
                fact_text = f"Note/Reminder: {fc.args.get('content') or fc.args.get('text')}"
                mem.save_fact(fact_text)
                logger.info(f"[BRAIN] Auto-learned: {fact_text}")

            # Correct wrapping for function responses as dicts
            tool_result_parts.append({
                "function_response": {
                    "name": fc.name,
                    "response": res if isinstance(res, dict) else {"result": str(res)}
                }
            })

            # Log for shared history
            call_id = f"call_{fc.name}_{uuid.uuid4().hex[:8]}"
            assistant_tool_calls_log.append({
                "id": call_id,
                "type": "function",
                "function": {"name": fc.name, "arguments": fc.args},
            })
            tool_result_msgs_log.append({"role": "tool", "name": fc.name, "content": str(res)})

        # Feed tool results back to Gemini for next step
        if tool_result_parts:
            contents.append({"role": "user", "parts": tool_result_parts})

    # Sync all tool interactions to shared history in one shot
    if assistant_tool_calls_log:
        assistant_msg = {
            "role": "assistant",
            "content": session_text.strip() or None,
            "tool_calls": assistant_tool_calls_log,
            "raw_parts": raw_parts, # PERSIST G3 STATE
        }
        add_tool_messages(assistant_msg, tool_result_msgs_log)

    yield {"type": "agent_done", "session_text": session_text.strip()}


# ── Public Entry Point ────────────────────────────────────────────────────────

async def process_stream(transcript: str) -> AsyncGenerator[dict, None]:
    """High-level Gemini stream with selective tools, real agent loop, and fallback."""

    # ── Reasoning pre-pass ────────────────────────────────────────────────────
    user_data    = mem.get_user()
    all_memories = [m for m in mem.get_all_memories()]
    result = await reason_async(
        transcript,
        all_memories,
        user_location=user_data.get("location", ""),
    )

    system_content = build_system_content()
    dynamic        = build_dynamic_context()
    
    # Inject dynamic context (Time, Memory) PERMANENTLY into the turn's user message.
    # This ensures history remains consistent and cache-friendly.
    final_input = f"[TURN_CONTEXT]\n{dynamic}\n\n{result.enriched_transcript}"
    add_user_message(final_input)

    # ── Tool selection (SELECTIVE ARSENAL for Neural Economy) ───────────────
    use_tools = not is_conversational(transcript)
    if use_tools:
        # We now use selective loading to save 1,500+ tokens per turn.
        # This keeps the context window tight and focuses the "Sir's" brain.
        from backend.brain.tools import get_tools_for_query
        tools = _convert_tools_to_gemini(get_tools_for_query(transcript))
    else:
        tools = []

    # ── Build session-scoped history ──────────────────────────────────────────
    # [TURN_CONTEXT] is now part of the history itself (see add_user_message below)
    # This allows prefix caching to work effectively across multiple turns.
    contents = _build_gemini_contents()

    # ── SESSION STARTUP DIAGNOSTIC ────────────────────────────────────────────
    # If this is the start of a session (only 1 user msg in history),
    # auto-inject a tactical report to provide JARVIS-style situational awareness.
    if len(get_history()) <= 1:
        from backend.plugins import execute_plugin_async
        diag = await execute_plugin_async("tactical_report", {})
        add_user_message(f"[STARTUP_DIAGNOSTIC]\n{diag}")
        # Re-build contents to include the diagnostic
        contents = _build_gemini_contents()
        logger.info("[BRAIN] Session startup: Tactical Diagnostic injected.")

    # ── Build client — raises ValueError with clear message on misconfiguration ─
    try:
        client, primary_model = _build_client()
    except ValueError as e:
        logger.error(f"[BRAIN] Client init failed: {e}")
        yield {"type": "error", "text": str(e)}
        return

    gemini_cfg    = cfg.get("gemini", {})
    use_lite      = gemini_cfg.get("use_lite_fallback", True)
    fallback_model = gemini_cfg.get("fallback_model", "gemini-2.0-flash-lite")

    session_text = ""

    async def _run(model: str):
        nonlocal session_text
        async for event in _run_agent_loop(client, contents, system_content, model, tools):
            if event["type"] == "agent_done":
                session_text = event["session_text"]
            else:
                yield event

    try:
        async for event in _run(primary_model):
            yield event

        final_text = session_text.strip() or "Done."
        add_assistant_message(final_text)
        yield {"type": "final_response", "value": final_text}

    except Exception as e:
        err_str = str(e)

        # Quota exceeded → retry with lite model
        if "429" in err_str and use_lite:
            logger.warning(f"[BRAIN] Quota hit on {primary_model}. Falling back to {fallback_model}.")
            session_text = ""
            try:
                async for event in _run(fallback_model):
                    yield event
                final_text = session_text.strip() or "Done."
                add_assistant_message(final_text)
                yield {"type": "final_response", "value": final_text}
            except Exception as fallback_e:
                logger.error(f"[BRAIN] Fallback also failed: {fallback_e}")
                yield {"type": "error", "text": f"Gemini Error (fallback): {str(fallback_e)}"}
        else:
            logger.error(f"[BRAIN] Gemini turn failed: {e}")
            yield {"type": "error", "text": f"Gemini Error: {err_str}"}