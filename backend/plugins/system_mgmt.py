"""
System Management Plugin — Common Windows maintenance commands wrapped safely.
"""

import subprocess
import threading
from backend.plugins._base import Plugin
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class SystemManagementPlugin(Plugin):
    name = "system_management"
    description = "Perform standard Windows maintenance tasks like Emptying the Recycle Bin, Locking the screen, or putting the PC to sleep."
    parameters = {
        "action": {
            "type": "string",
            "description": "The task to perform. Valid options: 'lock', 'sleep', 'empty_recycle_bin'",
            "enum": ["lock", "sleep", "empty_recycle_bin"],
            "required": True,
        },
    }

    def execute(self, action: str = "", **_) -> str:
        try:
            if action == "lock":
                subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"])
                return "Screen locked."

            elif action == "sleep":
                # We do this asynchronously so the assistant can say "going to sleep" before the OS suspends
                def _run():
                    import time
                    time.sleep(2)
                    subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
                threading.Thread(target=_run, daemon=True).start()
                return "Putting the computer to sleep."

            elif action == "empty_recycle_bin":
                ps_script = "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"
                res = subprocess.run(["powershell", "-WindowStyle", "Hidden", "-Command", ps_script], 
                                     creationflags=subprocess.CREATE_NO_WINDOW, capture_output=True, text=True)
                if res.returncode == 0:
                    return "Recycle Bin is now empty."
                else:
                    return "Recycle Bin was already empty or could not be cleared."
                    
            else:
                return f"Unsupported action: {action}"

        except Exception as e:
            logger.error(f"[SYSTEM_MGMT] Error: {e}")
            return f"System task failed: {str(e)[:100]}"
