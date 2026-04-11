"""
System Domain — Keyboard & Clipboard
"""

import subprocess
from backend.plugins._base import Plugin
from backend.utils.logger import get_logger

logger = get_logger(__name__)

class ClipboardPlugin(Plugin):
    name = "clipboard"
    description = "Copy text to clipboard."
    parameters = {"text": {"type": "string", "description": "Text to copy", "required": True}}

    def execute(self, text: str = "", **params) -> str:
        try:
            ps_text = text.replace('"', '`"')
            subprocess.run(["powershell", "-Command", f'Set-Clipboard "{ps_text}"'], creationflags=subprocess.CREATE_NO_WINDOW)
            return "Copied to clipboard."
        except Exception as e:
            logger.error(f"[CLIPBOARD] Failed: {e}")
            return "Failed to copy to clipboard."
