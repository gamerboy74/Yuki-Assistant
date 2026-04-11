"""
System Domain — App Management
"""

import os
import subprocess
from backend.plugins._base import Plugin
from backend.utils.logger import get_logger

logger = get_logger(__name__)

APP_MAP = {
    "chrome":           "chrome",
    "google chrome":    "chrome",
    "browser":          "chrome",
    "firefox":          "firefox",
    "edge":             "msedge",
    "microsoft edge":   "msedge",
    "notepad":          "notepad",
    "calculator":       "calc",
    "word":             "winword",
    "excel":            "excel",
    "powerpoint":       "powerpnt",
    "spotify":          "spotify",
    "discord":          "discord",
    "vlc":              "vlc",
    "vs code":          "code",
    "vscode":           "code",
    "visual studio code": "code",
    "code":             "code",
    "task manager":     "taskmgr",
    "file explorer":    "explorer",
    "explorer":         "explorer",
    "files":            "explorer",
    "control panel":    "control",
    "settings":         "ms-settings:",
    "terminal":         "wt",
    "cmd":              "cmd",
    "powershell":       "powershell",
    "whatsapp":         "whatsapp",
    "telegram":         "telegram",
    "zoom":             "zoom",
    "teams":            "msteams",
    "slack":            "slack",
    "photos":           "ms-photos:",
    "camera":           "microsoft.windows.camera:",
    "paint":            "mspaint",
}

KILL_MAP = {
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "firefox": "firefox.exe",
    "edge": "msedge.exe",
    "notepad": "notepad.exe",
    "spotify": "Spotify.exe",
    "discord": "Discord.exe",
    "vlc": "vlc.exe",
    "vscode": "Code.exe",
    "vs code": "Code.exe",
    "word": "WINWORD.EXE",
    "excel": "EXCEL.EXE",
    "powerpoint": "POWERPNT.EXE",
    "whatsapp": "WhatsApp.exe",
    "telegram": "Telegram.exe",
}

class OpenAppPlugin(Plugin):
    name = "open_app"
    description = "Open Windows app."
    parameters = {"name": {"type": "string", "description": "App name", "required": True}}

    def execute(self, name: str = "", **params) -> str:
        name = name.lower().strip()
        exe = APP_MAP.get(name, name)
        
        try:
            if "whatsapp" in name: os.startfile("whatsapp://")
            elif "spotify" in name: os.startfile("spotify:")
            elif ":" in exe: os.startfile(exe)
            else:
                subprocess.Popen(["start", "", exe], shell=True)
            return f"Opening {name}."
        except Exception as e:
            logger.error(f"[OPEN_APP] Failed: {e}")
            return f"Failed to open {name}."

class CloseAppPlugin(Plugin):
    name = "close_app"
    description = "Close Windows app."
    parameters = {"name": {"type": "string", "description": "App name", "required": True}}

    def execute(self, name: str = "", **params) -> str:
        name = name.lower().strip()
        proc = KILL_MAP.get(name, f"{name}.exe")
        try:
            subprocess.Popen(["taskkill", "/f", "/t", "/im", proc], shell=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return f"Closed {name}."
        except Exception as e:
            logger.error(f"[CLOSE_APP] Failed: {e}")
            return f"Failed to close {name}."
