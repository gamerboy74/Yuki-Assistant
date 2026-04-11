"""
System Domain — Power Control
"""

import subprocess
from backend.plugins._base import Plugin
from backend.utils.logger import get_logger

logger = get_logger(__name__)

class PowerControlPlugin(Plugin):
    name = "system_control"
    description = "Shutdown, Restart, or Sleep PC."
    parameters = {
        "action": {"type": "string", "enum": ["shutdown", "restart", "lock", "sleep"], "required": True},
        "confirm": {"type": "boolean", "description": "Must be true to execute destructive actions", "required": False}
    }

    def execute(self, action: str = "", confirm: bool = False, **params) -> str:
        action = action.lower().strip()
        
        if action in ["shutdown", "restart"] and not confirm:
            return f"Sir, please confirm the {action} sequence."
            
        try:
            if action == "lock":
                subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"])
                return "PC locked."
            elif action == "sleep":
                subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
                return "Going to sleep."
            elif action == "shutdown":
                subprocess.Popen(["shutdown", "/s", "/t", "30"])
                return "Shutdown sequence initiated. You have 30 seconds."
            elif action == "restart":
                subprocess.Popen(["shutdown", "/r", "/t", "30"])
                return "Restart sequence initiated. You have 30 seconds."
            return f"Action {action} initiated."
        except Exception as e:
            logger.error(f"[POWER] Failed {action}: {e}")
            return f"Failed to execute {action}."
