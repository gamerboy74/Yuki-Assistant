"""
Plugin auto-loader for Yuki.

At import time, scans this directory for all Plugin subclasses,
instantiates them, and builds a registry.

Usage:
    from backend.plugins import get_plugin, get_all_plugins, get_plugin_tools
    
    plugin = get_plugin("play_spotify")
    result = plugin.execute(query="Arijit Singh")
    
    tools = get_plugin_tools()  # list of OpenAI tool schemas
"""

from __future__ import annotations

import importlib
import os
import pkgutil
from typing import Optional
from backend.utils.logger import get_logger
from backend.plugins._base import Plugin

logger = get_logger(__name__)

# ── Registry ──────────────────────────────────────────────────────────────────
_registry: dict[str, Plugin] = {}


def _discover_plugins():
    """Scan this package directory, import all modules, register Plugin subclasses."""
    package_dir = os.path.dirname(__file__)

    for _, module_name, _ in pkgutil.iter_modules([package_dir]):
        if module_name.startswith("_"):
            continue  # skip _base.py etc.
        try:
            module = importlib.import_module(f"backend.plugins.{module_name}")
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, Plugin)
                    and attr is not Plugin
                    and attr.name  # must have a name set
                ):
                    instance = attr()
                    _registry[instance.name] = instance
                    logger.info(f"[PLUGINS] Registered: {instance.name}")
        except Exception as e:
            logger.warning(f"[PLUGINS] Failed to load plugin '{module_name}': {e}")


# Auto-discover at import time
_discover_plugins()


# ── Public API ────────────────────────────────────────────────────────────────

def get_plugin(name: str) -> Optional[Plugin]:
    """Get a registered plugin by name."""
    return _registry.get(name)


def get_all_plugins() -> dict[str, Plugin]:
    """Return the full plugin registry."""
    return dict(_registry)


def get_plugin_tools() -> list[dict]:
    """Generate OpenAI-compatible tool schemas for all registered plugins."""
    return [p.to_tool_schema() for p in _registry.values()]


def execute_plugin(name: str, params: dict) -> str:
    """Execute a plugin by name with the given params. Returns result string."""
    plugin = _registry.get(name)
    if not plugin:
        return f"Unknown plugin: '{name}'. Available: {', '.join(_registry.keys())}"
    try:
        return plugin.execute(**params)
    except Exception as e:
        logger.error(f"[PLUGINS] {name} error: {e}")
        return f"Plugin '{name}' failed: {str(e)[:150]}"
