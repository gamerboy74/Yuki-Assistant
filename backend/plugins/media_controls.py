"""
Media Controls Plugin — Global play/pause/skip with process-aware smart focus.
"""

import subprocess
import threading
import time
from typing import Optional, Tuple
from backend.plugins._base import Plugin
from backend.utils.logger import get_logger

logger = get_logger(__name__)

class MediaControlsPlugin(Plugin):
    name = "media_controls"
    description = "Play, pause, next, or previous media."
    parameters = {
        "action": {
            "type": "string",
            "description": "Media command: 'playpause', 'next', 'previous'",
            "enum": ["playpause", "next", "previous"],
            "required": True,
        },
    }

    def execute(self, action: str = "playpause", **_) -> str:
        # Map action to pyautogui keys
        key_map = {
            "playpause": "playpause",
            "next":      "nexttrack",
            "previous":  "prevtrack",
        }
        py_key = key_map.get(action, "playpause")
        
        # 1. Try smart detection and focus
        proc_name, pid = self._detect_audio_app()
        if pid:
            logger.info(f"[MEDIA] Targeting {proc_name} (pid={pid}) for {action}")
            if self._focus_and_press(pid, py_key):
                 return f"{action.capitalize()} triggered on {proc_name.replace('.exe', '')}."

        # 2. Fallback to global media key
        try:
            import pyautogui
            pyautogui.press(py_key)
            return f"{action.capitalize()}ing media globally."
        except Exception as e:
            logger.error(f"[MEDIA] Global control failed: {e}")
            return "Failed to control media."

    def _detect_audio_app(self) -> tuple[Optional[str], Optional[int]]:
        """Detect process name and PID currently producing audio via pycaw."""
        PRIORITY_APPS = ["Spotify", "chrome", "msedge", "firefox", "vlc", "groove"]
        try:
            from pycaw.pycaw import AudioUtilities
            from backend.utils.monitoring import PSUTIL_AVAILABLE, psutil
            if not PSUTIL_AVAILABLE:
                return None, None
            sessions = AudioUtilities.GetAllSessions()
            candidates = []
            for session in sessions:
                if session.Process is None: continue
                pid = session.Process.Id
                try:
                    proc = psutil.Process(pid)
                    name = proc.name()
                    base = name.lower().replace(".exe", "")
                    if session.State != 1: continue # 1 = Active
                    
                    priority = 99
                    for i, app in enumerate(PRIORITY_APPS):
                        if app.lower() in base:
                            priority = i
                            break
                    candidates.append((priority, name, pid))
                except Exception: continue
            
            if candidates:
                candidates.sort(key=lambda x: x[0])
                return candidates[0][1], candidates[0][2]
        except Exception: pass
        return None, None

    def _focus_and_press(self, pid: int, key: str) -> bool:
        """Briefly focus PID window and send media key via PowerShell."""
        key_code = {
            "playpause": "[char]179",
            "nexttrack": "[char]176",
            "prevtrack": "[char]177",
        }.get(key, "[char]179")
        try:
            script = (
                f"$wshell = New-Object -ComObject wscript.shell; "
                f"$proc = Get-Process -Id {pid} -ErrorAction SilentlyContinue; "
                f"if ($proc) {{ "
                f"  $wshell.AppActivate($proc.Id); Start-Sleep -Milliseconds 400; "
                f"  $wshell.SendKeys({key_code}); "
                f"  'ok' "
                f"}}"
            )
            res = subprocess.run(["powershell", "-WindowStyle", "Hidden", "-Command", script],
                                 capture_output=True, text=True, timeout=3,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
            return "ok" in res.stdout
        except Exception: return False
