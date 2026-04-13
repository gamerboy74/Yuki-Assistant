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
_discovered = False


def _discover_plugins():
    """Scan this package and subpackages for all Plugin subclasses."""
    global _discovered
    if _discovered:
        return

    package_dir = os.path.dirname(__file__)
    logger.debug(f"[PLUGINS] Starting recursive discovery in {package_dir}")

    # Recursive scan using pkgutil.walk_packages
    # This picks up backend.plugins.system.apps etc.
    for loader, module_name, is_pkg in pkgutil.walk_packages([package_dir], "backend.plugins."):
        try:
            module = importlib.import_module(module_name)
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, Plugin)
                    and attr is not Plugin
                    and getattr(attr, "name", None)  # must have a name set
                ):
                    instance = attr()
                    if instance.name not in _registry:
                        _registry[instance.name] = instance
                        logger.info(f"[PLUGINS] Registered: {instance.name}")
        except Exception as e:
            logger.warning(f"[PLUGINS] Failed to load module '{module_name}': {e}")

    _discovered = True
    logger.info(f"[PLUGINS] Discovery complete. Active Registry: {list(_registry.keys())}")



# Auto-discover once at import time
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


def execute_plugin(name: str, params: dict | str) -> str:
    """Execute a plugin by name with the given params. Returns result string."""
    import json
    plugin = _registry.get(name)
    if not plugin:
        return f"Unknown plugin: '{name}'. Available: {', '.join(_registry.keys())}"
    
    # Robustness: Attempt to parse if parameters are passed as a JSON string
    if isinstance(params, str):
        try:
            params = json.loads(params)
        except Exception as e:
            logger.warning(f"[PLUGINS] Failed to parse stringified params for {name}: {e}")
            # If it's not JSON, we treat it as an empty dict or a single 'query' param?
            # Standard is to expect a dict, so we'll try to recover or fail gracefully.
            params = {}

    try:
        return plugin.execute(**params)
    except Exception as e:
        logger.error(f"[PLUGINS] {name} error: {e}")
        return f"Plugin '{name}' failed: {str(e)[:150]}"
