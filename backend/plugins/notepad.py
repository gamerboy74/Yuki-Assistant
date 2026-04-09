"""
Notepad Plugin — A quick-capture inbox for saving notes to a text file.
"""

import os
from datetime import datetime
from backend.plugins._base import Plugin
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class NotepadPlugin(Plugin):
    name = "take_note"
    description = "Append a note to the Yuki_Notes.txt file on the user's Desktop. Use this whenever the user asks you to write something down or take a note."
    parameters = {
        "text": {
            "type": "string",
            "description": "The note content to save",
            "required": True,
        },
    }

    def execute(self, text: str = "", **_) -> str:
        if not text:
            return "What would you like me to write down?"

        try:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            notes_file = os.path.join(desktop, "Yuki_Notes.txt")
            
            # Timestamp the note
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            entry = f"[{timestamp}] {text}\n"

            with open(notes_file, "a", encoding="utf-8") as f:
                f.write(entry)

            logger.info(f"[NOTEPAD] Appended 1 note to Desktop/Yuki_Notes.txt")
            return "I've saved that to your notes."

        except Exception as e:
            logger.error(f"[NOTEPAD] Error: {e}")
            return f"Failed to save note: {str(e)[:100]}"
