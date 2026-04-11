"""WhatsApp plugin — send text messages and files via WhatsApp Desktop."""

import os
import subprocess
import time
from backend.plugins._base import Plugin
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class WhatsAppMessagePlugin(Plugin):
    name = "send_whatsapp"
    description = "Send WhatsApp text to contact name."
    parameters = {
        "contact": {
            "type": "string",
            "description": "Contact name as it appears in WhatsApp",
            "required": True,
        },
        "message": {
            "type": "string",
            "description": "Message text to send",
            "required": True,
        },
    }

    def execute(self, contact: str = "", message: str = "", **_) -> str:
        if not contact or not message:
            return "Need both a contact name and a message."

        try:
            import pyautogui

            os.startfile("whatsapp://")
            time.sleep(3.5)
            pyautogui.hotkey("ctrl", "f")
            time.sleep(0.5)
            pyautogui.typewrite(contact, interval=0.05)
            time.sleep(1.5)
            pyautogui.press("enter")
            time.sleep(1.0)
            pyautogui.typewrite(message, interval=0.02)
            pyautogui.press("enter")

            return f"Sent '{message}' to {contact} on WhatsApp."

        except ImportError:
            os.startfile("whatsapp://")
            return f"Opened WhatsApp but pyautogui is missing — please send manually to {contact}."
        except Exception as e:
            logger.error(f"WhatsApp error: {e}")
            return f"WhatsApp automation failed: {str(e)[:100]}"


class WhatsAppFilePlugin(Plugin):
    name = "send_whatsapp_file"
    description = "Send file to WhatsApp contact."
    parameters = {
        "contact": {
            "type": "string",
            "description": "Contact name",
            "required": True,
        },
        "file_path": {
            "type": "string",
            "description": "Full path to the file to send",
            "required": True,
        },
    }

    def execute(self, contact: str = "", file_path: str = "", **_) -> str:
        if not contact:
            return "Who should I send the file to?"
        if not file_path or not os.path.isfile(file_path):
            return f"File not found: {file_path}"

        try:
            import pyautogui

            # Copy file to clipboard
            ps_script = (
                "Add-Type -AssemblyName System.Windows.Forms; "
                "$col = New-Object System.Collections.Specialized.StringCollection; "
                f"$col.Add('{file_path}'); "
                "[System.Windows.Forms.Clipboard]::SetFileDropList($col)"
            )
            subprocess.run(
                ["powershell", "-WindowStyle", "Hidden", "-Command", ps_script],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            time.sleep(0.5)

            os.startfile("whatsapp://")
            time.sleep(3.5)
            pyautogui.hotkey("ctrl", "f")
            time.sleep(0.5)
            pyautogui.typewrite(contact, interval=0.05)
            time.sleep(1.5)
            pyautogui.press("enter")
            time.sleep(1.2)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(2.0)
            pyautogui.press("enter")
            time.sleep(0.8)

            fname = os.path.basename(file_path)
            return f"Sent '{fname}' to {contact} via WhatsApp."

        except ImportError:
            return "pyautogui not installed — can't automate WhatsApp."
        except Exception as e:
            logger.error(f"WhatsApp file error: {e}")
            return f"WhatsApp file send failed: {str(e)[:100]}"
