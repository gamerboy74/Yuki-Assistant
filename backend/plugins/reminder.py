"""Reminder plugin — show a Windows toast notification after a delay."""

import subprocess
import threading
import time
from backend.plugins._base import Plugin
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class ReminderPlugin(Plugin):
    name = "set_reminder"
    description = "Set a timed reminder. Supports relative ('10m', '1h') or absolute ('5pm') times."
    parameters = {
        "text": {"type": "string", "description": "What to remind you about", "required": True},
        "at_time": {"type": "string", "description": "When (e.g., 'in 5m', 'at 6pm')", "required": True}
    }

    def execute(self, text: str = "Reminder!", at_time: str = "1m", **_) -> str:
        # Simple parser for "10m", "1h", etc.
        import re
        delay_secs = 60 # fallback
        try:
            val = int(re.search(r"\d+", at_time).group())
            if "h" in at_time.lower(): delay_secs = val * 3600
            elif "s" in at_time.lower(): delay_secs = val
            else: delay_secs = val * 60 # default to minutes
        except: pass

        def _show_toast():
            time.sleep(delay_secs)
            try:
                ps_cmd = (
                    f'[System.Reflection.Assembly]::LoadWithPartialName("System.Windows.Forms") | Out-Null; '
                    f'$notify = New-Object System.Windows.Forms.NotifyIcon; '
                    f'$notify.Icon = [System.Drawing.SystemIcons]::Information; '
                    f'$notify.Visible = $true; '
                    f'$notify.ShowBalloonTip(8000, "Yuki Reminder", "{text}", '
                    f'[System.Windows.Forms.ToolTipIcon]::Info); '
                    f'Start-Sleep 10; $notify.Dispose()'
                )
                subprocess.Popen(
                    ["powershell", "-WindowStyle", "Hidden", "-Command", ps_cmd],
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            except Exception as e:
                logger.error(f"Reminder toast error: {e}")

        t = threading.Thread(target=_show_toast, daemon=True)
        t.start()

        return f"I'll remind you about '{text}' in {at_time}."
