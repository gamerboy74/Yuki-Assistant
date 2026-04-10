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
    is_conversational,
    add_user_message,
    add_assistant_message,
    add_tool_messages,
    get_openai_messages,
)
from backend.brain.tools import get_tools_for_query

logger = get_logger(__name__)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

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
    """
    Async generator that yields Brain events:
    - {'type': 'text_sentence', 'value': '...'}
    - {'type': 'tool_start', 'value': '...'}
    - {'type': 'tool_end', 'value': '...'}
    - {'type': 'final_response', 'value': '...'}
    """
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    add_user_message(transcript)

    system_content = build_system_content()

    # ── Chat-only fast path: skip tools for conversational queries ─────────
    # Saves ~2,000 tokens by not sending any tool schemas.
    use_tools = not is_conversational(transcript)

    # ── Selective tool loading ────────────────────────────────────────────
    tools = get_tools_for_query(transcript) if use_tools else None

    # Avoid redundant retries of the exact same tool calls within a single turn.
    executed_tool_calls: dict[tuple[str, str], str] = {}

    for step in range(MAX_AGENT_STEPS):
        messages = get_openai_messages(system_content)

        create_kwargs = {
            "model": OPENAI_MODEL,
            "messages": messages,
            "stream": True,
            "temperature": 0.4,
        }
        if tools:
            create_kwargs["tools"] = tools

        stream = await client.chat.completions.create(**create_kwargs)

        streamer = _SentenceStreamer()
        full_content = ""
        current_tool_calls: dict[int, dict] = {}

        async for chunk in stream:
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
            "content": full_content or None,
            "tool_calls": [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc["arguments"]},
                }
                for tc in current_tool_calls.values()
            ],
        }

        from backend.tools.dispatcher import dispatch_tool

        tool_result_msgs: list[dict] = []
        for tc in current_tool_calls.values():
            signature = (tc["name"], tc["arguments"].strip())
            if signature in executed_tool_calls:
                res = executed_tool_calls[signature]
            else:
                res = await asyncio.to_thread(dispatch_tool, tc["name"], tc["arguments"])
                executed_tool_calls[signature] = res

            tool_result_msgs.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": str(res),
            })
            yield {"type": "tool_end", "value": tc["name"]}

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
