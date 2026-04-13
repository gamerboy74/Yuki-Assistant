"""
Computer Hands Plugin — Low-level OS control (Keyboard, Mouse, Native UI).
"""

import time
import subprocess
from typing import Optional
from backend.plugins._base import Plugin
from backend.utils.logger import get_logger

logger = get_logger(__name__)

class ComputerHandsPlugin(Plugin):
    name = "computer_hands"
    description = "Control mouse, keyboard, and Windows UI."
    parameters = {
        "operation": {
            "type": "string",
            "description": "Task: type_text, key_shortcut, click, move_mouse, smart_navigate, click_at, clipboard",
            "required": True
        },
        "text": {"type": "string", "description": "Text to type or copy", "required": False},
        "keys": {"type": "array", "items": {"type": "string"}, "description": "Keys for shortcut", "required": False},
        "target": {"type": "string", "description": "UI element name for smart_navigate", "required": False},
        "action": {"type": "string", "description": "For clipboard: 'copy' or 'paste'", "required": False},
        "x": {"type": "integer", "description": "X coordinate", "required": False},
        "y": {"type": "integer", "description": "Y coordinate", "required": False},
    }

    def execute(self, operation: str = "", **params) -> str:
        try:
            import pyautogui
            pyautogui.FAILSAFE = True
            
            if operation == "type_text":
                import pyperclip
                text = params.get("text", "")
                time.sleep(1.0)  # Give the active window time to be ready for input
                
                # Unicode-safe: paste via clipboard if non-ASCII detected
                if any(ord(c) >= 128 for c in text):
                    pyperclip.copy(text)
                    pyautogui.hotkey("ctrl", "v")
                else:
                    pyautogui.typewrite(text, interval=0.02)

                return f"Typed: '{text[:40]}...'" if len(text) > 40 else f"Typed: '{text}'"


            elif operation == "key_shortcut":
                keys = params.get("keys", [])
                if not keys: return "No keys specified."
                pyautogui.hotkey(*keys)
                return f"Pressed: {' + '.join(keys)}"

            elif operation == "smart_navigate":
                return self._smart_navigate(params)

            elif operation == "click":
                pyautogui.click()
                return "Clicked."

            elif operation == "move_mouse":
                x, y = params.get("x", 0), params.get("y", 0)
                pyautogui.moveTo(x, y, duration=0.25)
                return f"Moved mouse to {x}, {y}"

            elif operation == "click_at":
                x, y = params.get("x", 0), params.get("y", 0)
                pyautogui.click(x, y)
                return f"Clicked at coordinates {x}, {y}"

            elif operation == "clipboard":
                import pyperclip
                action = params.get("action", "paste")
                if action == "copy":
                    pyperclip.copy(params.get("text", ""))
                    return "Copied to clipboard."
                else:
                    return f"Clipboard content: {pyperclip.paste()}"

            return f"Unknown operation: {operation}"
        except Exception as e:
            logger.error(f"[HANDS] Error: {e}")
            return f"Action failed: {str(e)[:100]}"

    def _smart_navigate(self, params: dict) -> str:
        """Native UI tree navigation via pywinauto."""
        try:
            from pywinauto import Desktop
            target = params.get("target", "").lower()
            
            windows = Desktop(backend="uia").windows()
            active_win = next((w for w in windows if w.is_active()), None)
            if not active_win: return "No active window found."

            try:
                elem = active_win.child_window(title_re=f".*{target}.*", control_type="Button")
                elem.click_input()
                return f"Clicked '{target}' in {active_win.window_text()}."
            except Exception:
                return f"Could not find button '{target}'."
        except Exception as e:
            return f"Smart navigate failed: {e}"

class TypeTextPlugin(ComputerHandsPlugin):
    name = "type_text"
    description = "Type text on keyboard."
    parameters = {"text": {"type": "string", "description": "Text to type", "required": True}}
    def execute(self, text: str = "", **params) -> str:
        return super().execute(operation="type_text", text=text, **params)

class KeyShortcutPlugin(ComputerHandsPlugin):
    name = "key_shortcut"
    description = "Press keyboard shortcut."
    parameters = {"keys": {"type": "array", "items": {"type": "string"}, "description": "Keys (e.g. ['ctrl', 'c'])", "required": True}}
    def execute(self, keys: list = None, **params) -> str:
        return super().execute(operation="key_shortcut", keys=keys or [], **params)

class SmartNavigatePlugin(ComputerHandsPlugin):
    name = "smart_navigate"
    description = "Click/focus UI element by name."
    parameters = {
        "target": {"type": "string", "description": "Name of the button or item", "required": True},
        "action": {"type": "string", "enum": ["click", "focus"], "default": "click"}
    }
    def execute(self, target: str = "", action: str = "click", **params) -> str:
        return self._smart_navigate({"target": target, "action": action, **params})
