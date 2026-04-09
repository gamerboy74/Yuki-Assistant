from backend.plugins._base import Plugin
from backend.utils.logger import get_logger

logger = get_logger(__name__)

class ComputerHandsPlugin(Plugin):
    """
    Physical mouse and keyboard control capabilities relying on pyautogui.
    """
    
    def get_definitions(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "mouse_move",
                    "description": "Move the mouse to absolute screen coordinates. The screen originates at (0,0) in the top left.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "x": {"type": "integer", "description": "X coordinate in pixels"},
                            "y": {"type": "integer", "description": "Y coordinate in pixels"}
                        },
                        "required": ["x", "y"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "mouse_click",
                    "description": "Click the mouse at the current position.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "button": {
                                "type": "string",
                                "enum": ["left", "right", "middle"],
                                "description": "Which mouse button to click"
                            },
                            "clicks": {
                                "type": "integer",
                                "description": "Number of times to click (1 for single, 2 for double)"
                            }
                        },
                        "required": ["button"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "keyboard_type",
                    "description": "Type a string of text using the keyboard as if the user typed it.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string", "description": "The exact text to type"},
                            "press_enter": {"type": "boolean", "description": "Whether to press Enter automatically after typing"}
                        },
                        "required": ["text"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "keyboard_shortcut",
                    "description": "Press a combination of keys (e.g. ['ctrl', 'c'] or ['win', 'r']).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "keys": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of key names to press together"
                            }
                        },
                        "required": ["keys"]
                    }
                }
            }
        ]

    def execute(self, action: str, params: dict) -> str:
        try:
            import pyautogui
            # Fail-safe: moving mouse to 0,0 cancels pyautogui
            pyautogui.FAILSAFE = True

            if action == "mouse_move":
                x, y = params.get("x", 0), params.get("y", 0)
                pyautogui.moveTo(x, y, duration=0.25)
                return f"Mouse moved to {x}, {y}"

            elif action == "mouse_click":
                button = params.get("button", "left")
                clicks = params.get("clicks", 1)
                pyautogui.click(button=button, clicks=clicks)
                return f"Mouse clicked {button} {clicks} times"

            elif action == "keyboard_type":
                text = params.get("text", "")
                press_enter = params.get("press_enter", False)
                pyautogui.write(text, interval=0.01)
                if press_enter:
                    pyautogui.press("enter")
                return f"Typed: '{text}'" + (" and hit Enter" if press_enter else "")

            elif action == "keyboard_shortcut":
                keys = params.get("keys", [])
                if not keys:
                    return "No keys provided."
                # Translate 'win' to 'winleft' if pyAutoGUI expects it, though 'win' usually works
                # execute hotkey
                pyautogui.hotkey(*keys)
                return f"Pressed shortcut: {' + '.join(keys)}"

        except Exception as e:
            logger.error(f"PyAutoGUI Error: {e}")
            return f"Action failed: {e}"
        
        return "Action not supported."
