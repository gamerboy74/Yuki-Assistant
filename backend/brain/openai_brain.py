"""
brain/openai_brain.py — GPT-4o-mini with Agentic Tool Loop.

Uses shared infrastructure for prompt, history, and tool selection.
Token-optimized: selective tool loading + chat fast path.

Architecture:
  1. Chat-only fast path: conversational queries skip tools entirely (-2,000 tokens)
  2. Selective tools: only relevant tools loaded per query (-1,500 tokens)
  3. Compressed prompt + truncated history: (-1,400 tokens)
  4. Agentic loop: up to 5 steps for multi-step tasks
"""

import os
import re
import asyncio
from typing import AsyncGenerator
from backend.utils.logger import get_logger
from backend.brain.shared import (
    build_system_content,
    build_dynamic_context,
    is_conversational,
    add_user_message,
    add_assistant_message,
    add_tool_messages,
    get_openai_messages,
)
from backend.brain.tools import get_tools_for_query
from backend.brain.reasoning import reason_async, track_execution
from backend import memory as mem
from backend.config import cfg

logger = get_logger(__name__)

# Note: Model ID is pulled from cfg dynamically to allow dashboard hot-swapping
MAX_AGENT_STEPS = 5  # Down from 8 — 5 is sufficient for complex tasks


class _SentenceStreamer:
    """Chunks a stream of tokens into full sentences for natural TTS."""

    _SPLIT_RE = re.compile(r"(?<=[.!?])(\s+|\n)")

    def __init__(self):
        self.buffer = ""

    def push(self, token: str) -> str | None:
        self.buffer += token
        match = self._SPLIT_RE.search(self.buffer)
        if match:
            end_idx = match.end()
            res = self.buffer[:end_idx].strip()
            self.buffer = self.buffer[end_idx:]
            if len(res) > 1:
                return res
        return None

    def flush(self) -> str | None:
        res = self.buffer.strip()
        self.buffer = ""
        return res if res else None


async def process_stream(transcript: str) -> AsyncGenerator[dict, None]:
    """Agentic tool loop for OpenAI."""
    from openai import AsyncOpenAI
    
    # Dynamically pull model-id and API key from config/env
    api_key = cfg.get("openai", {}).get("openai_api_key") or os.environ.get("OPENAI_API_KEY", "")
    active_model = cfg.get("openai", {}).get("model", "gpt-4o-mini")
    
    if not api_key:
        yield {"type": "error", "text": "OpenAI API key is not configured in Settings."}
        return

    client = AsyncOpenAI(api_key=api_key)
    
    # ── Reasoning Layer (JARVIS-style pre-processing) ──────────────────────────
    user_data    = mem.get_user()
    all_memories = [m for m in mem.get_all_memories()]
    result = await reason_async(
        transcript,
        all_memories,
        user_location=user_data.get("location", ""),
    )
    add_user_message(result.enriched_transcript)

    system_content = build_system_content()

    # ── Chat-only fast path: skip tools for conversational queries ─────────
    # Saves ~2,000 tokens by not sending any tool schemas.
    # Keep transcript clean for the conversational check
    use_tools = not is_conversational(transcript)

    # ── Selective tool loading ────────────────────────────────────────────
    tools = get_tools_for_query(transcript) if use_tools else None

    # Avoid redundant retries of the exact same tool calls within a single turn.
    executed_tool_calls: dict[tuple[str, str], str] = {}

    for step in range(MAX_AGENT_STEPS):
        messages = get_openai_messages(system_content)
        
        # ── Neural Economy: Caching-Friendly Context Injection ─────────────────
        # Inject context into the user's message instead of a prefix message.
        # This keeps the system prompt at index 0 static for cache hits.
        dynamic = build_dynamic_context()
        if dynamic:
            # Find the most recent user message and prepend the context
            for msg in reversed(messages):
                if msg["role"] == "user":
                    msg["content"] = f"[TURN_CONTEXT]\n{dynamic}\n\n{msg['content']}"
                    break

        create_kwargs = {
            "model": active_model,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
            "temperature": 0.4,
        }
        if tools:
            create_kwargs["tools"] = tools

        try:
            stream = await client.chat.completions.create(**create_kwargs)
        except Exception as e:
            logger.error(f"[OPENAI] API call failed: {e}")
            if hasattr(e, "body") and e.body:
                logger.error(f"[OPENAI] ERROR BODY: {e.body}")
            raise e

        streamer = _SentenceStreamer()
        full_content = ""
        current_tool_calls: dict[int, dict] = {}

        async for chunk in stream:
            # Handle Usage (OpenAI 1.26.0+ with stream_options)
            if hasattr(chunk, "usage") and chunk.usage:
                details = getattr(chunk.usage, "prompt_tokens_details", None)
                cached = getattr(details, "cached_tokens", 0) if details else 0
                yield {
                    "type": "usage",
                    "model": active_model,
                    "input": chunk.usage.prompt_tokens,
                    "output": chunk.usage.completion_tokens,
                    "cached": cached
                }

            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta

            # Handle Text
            if delta.content:
                full_content += delta.content
                sentence = streamer.push(delta.content)
                if sentence:
                    yield {"type": "text_sentence", "value": sentence}

            # Handle Tool Calls (Streaming)
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    if tc.id:
                        current_tool_calls[tc.index] = {
                            "id": tc.id,
                            "name": tc.function.name,
                            "arguments": "",
                        }
                        yield {"type": "tool_start", "value": tc.function.name}
                    if tc.function and tc.function.arguments:
                        current_tool_calls[tc.index]["arguments"] += tc.function.arguments

        # Flush remaining text
        last_sentence = streamer.flush()
        if last_sentence:
            yield {"type": "text_sentence", "value": last_sentence}

        # If no tool calls, we are done
        if not current_tool_calls:
            add_assistant_message(full_content)
            yield {"type": "final_response", "value": full_content}
            return

        # ── Execute Tool Calls in Parallel ─────────────────────────────────
        assistant_msg = {
            "role": "assistant",
            "content": full_content if full_content else None,
            "tool_calls": [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc["arguments"]},
                }
                for tc in current_tool_calls.values()
            ],
        }

        from backend.plugins import execute_plugin_async

        tool_result_msgs: list[dict] = []
        for tc in current_tool_calls.values():
            signature = (tc["name"], tc["arguments"].strip())
            if signature in executed_tool_calls:
                res = executed_tool_calls[signature]
            else:
                import json
                try:
                    args = json.loads(tc["arguments"])
                except Exception as e:
                    logger.warning(f"[OPENAI] Tool argument parse failed: {e}")
                    args = {}
                
                # Use dedicated thread pool to prevent Playwright greenlet bugs
                
                # We do them sequentially for OpenAI out of simplicity for now, or parallel
                # but await execute_plugin_async is safe.
                res = await execute_plugin_async(tc["name"], args)
                executed_tool_calls[signature] = res
                
                # Behavioral Learning: Track successful execution to learn user patterns
                track_execution(tc["name"])

            tool_result_msgs.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": str(res),
            })
            yield {"type": "tool_end", "value": tc["name"]}

            # ── Sentient Auto-Learning ──
            if tc["name"] in ["notepad", "reminder", "set_reminder"] and "saved" in str(res).lower():
                import json
                try: 
                    args = json.loads(tc["arguments"])
                except: 
                    args = {}
                fact_text = f"Note/Reminder: {args.get('content') or args.get('text')}"
                mem.save_fact(fact_text)
                logger.debug(f"[OPENAI] Auto-Learned: {fact_text}")

        # Record in shared history (with truncation)
        add_tool_messages(assistant_msg, tool_result_msgs)

        # Loop back for next agentic step
        continue

    # Exhausted tool steps
    fallback = (
        "I couldn't fully complete that after several tool attempts. "
        "I can still help if you want me to retry with a simpler request."
    )
    add_assistant_message(fallback)
    yield {"type": "final_response", "value": fallback}
