"""
Plugin base class for Yuki.

Every plugin is a self-contained capability that:
  1. Declares its name, description, and parameter schema
  2. Implements an execute() method
  3. Gets auto-discovered by the plugin loader

To add a new skill: create a .py file in backend/plugins/, subclass Plugin,
fill in the metadata, implement execute(). That's it — no other files to touch.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any


class Plugin(ABC):
    """Base class for all Yuki plugins."""

    # ── Metadata (override in subclasses) ─────────────────────────────────
    name: str = ""                  # unique identifier, e.g. "play_spotify"
    description: str = ""           # short description shown to the LLM
    parameters: dict[str, Any] = {} # JSON-schema-style param definitions

    @abstractmethod
    def execute(self, **params) -> str:
        """
        Run the plugin action. Return a human-readable result string.
        This string is fed back to the LLM so it knows what happened.
        """
        ...

    def to_tool_schema(self) -> dict:
        """Generate an OpenAI-compatible function tool schema from metadata."""
        props = {}
        required = []
        for param_name, param_info in self.parameters.items():
            props[param_name] = {
                "type": param_info.get("type", "string"),
                "description": param_info.get("description", ""),
            }
            if param_info.get("required", False):
                required.append(param_name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": props,
                    "required": required,
                },
            },
        }
