"""
Executor — routes brain actions to standardized plugins.
Standardizes on the backend/plugins/ architecture.
"""

from typing import Optional, Union, Callable
from backend.utils.logger import get_logger
from backend import plugins

logger = get_logger(__name__)

def execute(action: dict, send_fn: Optional[Callable[[dict], None]] = None) -> Union[str, dict, None]:
    """
    Execute an action returned by the brain.
    Returns an optional override response string, or None.

    action format: {"type": "action_name", "params": {...}}
    send_fn: optional callable(dict) for IPC — uses print fallback if None.
    """
    atype = action.get("type", "none")
    params = action.get("params", {})

    logger.info(f"Executing: {atype} | params: {params}")

    def _send(msg: dict):
        if send_fn:
            send_fn(msg)
        else:
            import json
            try:
                # Fallback to stdout for CLI testing
                print(json.dumps(msg), flush=True)
            except Exception:
                pass

    if atype != "none":
        _send({"type": "loading", "text": f"RUNNING {atype.upper().replace('_', ' ')}..."})
    else:
        return None

    # Dispatch to the plugin system
    # The plugin system handles metadata, safety, and execution.
    try:
        result = plugins.execute_plugin(atype, params)
        return result
    except Exception as e:
        logger.error(f"[EXECUTOR] Dispatch error ({atype}): {e}")
        return f"I encountered a problem running {atype}: {str(e)[:100]}"
