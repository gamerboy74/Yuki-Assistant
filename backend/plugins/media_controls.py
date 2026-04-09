"""
Media Controls Plugin — Global play/pause/skip for background music and videos.
"""

import subprocess
import threading
from backend.plugins._base import Plugin
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class MediaControlsPlugin(Plugin):
    name = "media_controls"
    description = "Control global media playback (e.g., Spotify, YouTube, VLC). Use to play, pause, next track, or previous track."
    parameters = {
        "action": {
            "type": "string",
            "description": "The media action to perform. Valid options: 'playpause', 'next', 'previous'",
            "enum": ["playpause", "next", "previous"],
            "required": True,
        },
    }

    def execute(self, action: str = "playpause", **_) -> str:
        if action not in ["playpause", "next", "previous"]:
            return f"Invalid action '{action}'. Use playpause, next, or previous."

        # Map action to Windows virtual key codes
        keys = {
            "playpause": "playpause",
            "next": "nexttrack",
            "previous": "prevtrack",
        }
        
        target_key = keys[action]

        try:
            import pyautogui
            pyautogui.press(target_key)
            
            action_desc = "Playing/Pausing" if action == "playpause" else f"Skipping to {action} track"
            return f"{action_desc} media..."

        except ImportError:
            return "pyautogui is required for media controls."
        except Exception as e:
            logger.error(f"[MEDIA] Error: {e}")
            return f"Failed to send media key: {str(e)[:100]}"
