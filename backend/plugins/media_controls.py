"""
media_controls.py — Specialized Media Playback Control
"""

import pyautogui
from backend.plugins._base import Plugin
from backend.utils.logger import get_logger

logger = get_logger(__name__)

class MediaControlPlugin(Plugin):
    name = "media_controls"
    description = "Control media playback (pause, resume, next, back)."
    parameters = {
        "action": {
            "type": "string", 
            "enum": ["playpause", "next", "prev"],
            "required": True
        }
    }

    def execute(self, action: str = "playpause", **_) -> str:
        try:
            if action == "playpause": pyautogui.press("playpause")
            elif action == "next": pyautogui.press("nexttrack")
            elif action == "prev": pyautogui.press("prevtrack")
            return f"Media {action} signal sent, Sir."
        except Exception as e:
            logger.error(f"[MEDIA] {e}")
            return f"Media control failed: {e}"
