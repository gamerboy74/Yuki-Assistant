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
    "brave":            "brave",
    "brave browser":    "brave",
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
    "brave": "brave.exe",
    "brave browser": "brave.exe",
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
        # ── Domain Guard ──
        if "." in name and not any(app in name for app in ["discord", "vs code", "vscode"]):
             return f"Sir, '{name}' appears to be a website rather than an application. I should use the browser navigation protocol for this."
             
        exe = APP_MAP.get(name, name)
        
        try:
            if "whatsapp" in name: os.startfile("whatsapp://")
            elif "spotify" in name: os.startfile("spotify:")
            elif ":" in exe: os.startfile(exe)
            else:
                subprocess.Popen(["start", "", exe], shell=True)
            
            # Focus Stabilization: Give Windows time to launch and focus the GUI
            if name in ["notepad", "word", "excel", "spotify", "discord", "chrome"]:
                import time
                time.sleep(2.5)  # Increased from 1.5s — gives Notepad time to fully init

            # ── Notepad Focus Lock ──
            # After launch, actively bring Notepad to the foreground so subsequent
            # type_text calls land in Notepad, not the Electron window.
            if name == "notepad":
                try:
                    import pygetwindow as gw
                    wins = gw.getWindowsWithTitle("Notepad")
                    if wins:
                        w = wins[-1]  # Get the most recently opened Notepad
                        w.restore()
                        w.activate()
                        import time; time.sleep(0.3)
                        logger.info(f"[OPEN_APP] Notepad focused: '{w.title}'")
                except Exception as focus_err:
                    logger.warning(f"[OPEN_APP] Could not focus Notepad: {focus_err}")
                
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

class CloseActiveWindowPlugin(Plugin):
    name = "close_active_window"
    description = "Close the currently active window (Alt+F4)."
    parameters = {}

    def execute(self, **params) -> str:
        try:
            import pyautogui
            pyautogui.hotkey('alt', 'f4')
            return "Closed the active window, Sir."
        except Exception as e:
            logger.error(f"[CLOSE_ACTIVE] Failed: {e}")
            return "Failed to close the active window."
