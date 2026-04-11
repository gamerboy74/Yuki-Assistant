"""
System Domain — Audio & Display
"""

import subprocess
from backend.plugins._base import Plugin
from backend.utils.logger import get_logger

logger = get_logger(__name__)

class SetVolumePlugin(Plugin):
    name = "set_volume"
    description = "Adjust volume (0-100)."
    parameters = {"level": {"type": "integer", "description": "Volume level", "required": True}}

    def execute(self, level: int = 50, **params) -> str:
        level = max(0, min(100, int(level)))
        try:
            # Use simple PowerShell level set
            script = f"$obj=New-Object -ComObject WScript.Shell;for($i=0;$i -lt 50;$i++){{$obj.SendKeys([char]174)}};for($i=0;$i -lt {int(level/2)};$i++){{$obj.SendKeys([char]175)}}"
            subprocess.Popen(["powershell", "-WindowStyle", "Hidden", "-Command", script], creationflags=subprocess.CREATE_NO_WINDOW)
            return f"Volume set to {level}%."
        except Exception as e:
            logger.error(f"[VOLUME] Failed: {e}")
            return "Failed to set volume."

class SetBrightnessPlugin(Plugin):
    name = "set_brightness"
    description = "Adjust brightness (0-100)."
    parameters = {"level": {"type": "integer", "description": "Brightness level", "required": True}}

    def execute(self, level: int = 50, **params) -> str:
        level = max(0, min(100, int(level)))
        try:
            script = f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{level})"
            subprocess.Popen(["powershell", "-WindowStyle", "Hidden", "-Command", script], creationflags=subprocess.CREATE_NO_WINDOW)
            return f"Brightness set to {level}%."
        except Exception as e:
            logger.error(f"[BRIGHTNESS] Failed: {e}")
            return "Failed to set brightness."
