"""
brain/tools.py — Dynamic Plugin-based Tool Registry for Yuki.

This module now pulls schemas directly from the Plugin Registry, 
ensuring zero redundancy and perfect alignment between capabilities 
and execution.
"""

import re
from typing import Any
from backend.utils.logger import get_logger
from backend.plugins import get_all_plugins

logger = get_logger(__name__)


def get_tools_for_query(transcript: str) -> list[dict]:
    """
    Return all available tools for every query.
    Gemini handles the full toolset efficiently.
    """
    return get_all_tools()

def get_all_tools() -> list[dict]:
    """Return all available plugins as tools."""
    all_plugins = get_all_plugins()
    return [p.to_tool_schema() for p in all_plugins.values()]

