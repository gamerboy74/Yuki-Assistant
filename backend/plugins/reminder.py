"""Reminder plugin — show a Windows toast notification after a delay."""

import subprocess
import threading
import time
from backend.plugins._base import Plugin
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class ReminderPlugin(Plugin):
    name = "reminder"
    description = "Set a timed reminder. Shows a Windows toast notification after the specified delay."
    parameters = {
        "text": {
            "type": "string",
            "description": "What to remind the user about",
            "required": True,
        },
        "delay_minutes": {
            "type": "integer",
            "description": "Number of minutes from now",
            "required": True,
        },
    }

    def execute(self, text: str = "Reminder!", delay_minutes: int = 1, **_) -> str:
        delay_minutes = max(0, int(delay_minutes))
        delay_secs = delay_minutes * 60

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

        if delay_minutes < 1:
            when = f"{int(delay_secs)}s"
        elif delay_minutes == 1:
            when = "1 minute"
        else:
            when = f"{delay_minutes} minutes"

        return f"I'll remind you about '{text}' in {when}."
