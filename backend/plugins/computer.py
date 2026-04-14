"""
computer.py — Keyboard, Mouse, and Window Control
Consolidates computer_hands features into a single mega-tool.
"""

import time
import pyperclip
import pyautogui
from backend.plugins._base import Plugin
from backend.utils.logger import get_logger

logger = get_logger(__name__)

class ComputerPlugin(Plugin):
    name = "computer"
    description = """Control keyboard, mouse, clipboard, and application windows.
Operations:
  type_text [text: str] — types text (Unicode safe, works with Hindi/emoji)
  key_shortcut [keys: list] — press shortcut e.g. ['ctrl','c']
  click — click current mouse position
  click_at [x: int, y: int] — click at coordinates
  move_mouse [x: int, y: int] — move mouse
  clipboard_read — read current clipboard content
  clipboard_write [text: str] — write text to clipboard
  window_list — list all open windows
  window_focus [app: str] — bring window to foreground
  window_minimize [app: str]
  window_maximize [app: str]
  window_close [app: str]
  window_snap_left [app: str]
  window_snap_right [app: str]
"""
    parameters = {
        "operation": {
            "type": "string", "required": True,
            "enum": ["type_text","key_shortcut","click","click_at","move_mouse",
                     "clipboard_read","clipboard_write","window_list","window_focus",
                     "window_minimize","window_maximize","window_close","window_snap_left","window_snap_right"]
        },
        "text": {"type": "string", "description": "Text to type or copy"},
        "keys": {"type": "array", "items": {"type": "string"}, "description": "Keys (e.g. ['ctrl', 'c'])"},
        "app": {"type": "string", "description": "Partial window title"},
        "x": {"type": "integer"},
        "y": {"type": "integer"}
    }

    def __init__(self):
        pyautogui.FAILSAFE = True

    def execute(self, operation: str = "", **params) -> str:
        try:
            # ── Keyboard ──
            if operation == "type_text":
                text = params.get("text", "")
                if not text: return "No text provided."
                # CRITICAL: Always use clipboard paste for Unicode safety (Hindi, Emoji)
                pyperclip.copy(text)
                time.sleep(0.2)
                pyautogui.hotkey("ctrl", "v")
                return f"Typed content, Sir."

            if operation == "key_shortcut":
                keys = params.get("keys", [])
                if not keys: return "No keys provided."
                pyautogui.hotkey(*keys)
                return f"Pressed shortcut: {'+'.join(keys)}."

            # ── Mouse ──
            if operation == "click":
                pyautogui.click()
                return "Clicked."
            
            if operation == "click_at":
                x, y = params.get("x", 0), params.get("y", 0)
                pyautogui.click(x, y)
                return f"Clicked at {x}, {y}."
            
            if operation == "move_mouse":
                x, y = params.get("x", 0), params.get("y", 0)
                pyautogui.moveTo(x, y, duration=0.25)
                return f"Moved mouse to {x}, {y}."

            # ── Clipboard ──
            if operation == "clipboard_read":
                return f"Clipboard: {pyperclip.paste()}"
            
            if operation == "clipboard_write":
                pyperclip.copy(params.get("text", ""))
                return "Saved to clipboard."

            # ── Window Management ──
            import pygetwindow as gw
            
            if operation == "window_list":
                titles = [w.title for w in gw.getAllWindows() if w.title]
                return "Open Windows:\n" + "\n".join(titles[:20])
            
            app_query = params.get("app", "")
            if app_query:
                # Case-insensitive partial match
                wins = [w for w in gw.getWindowsWithTitle(app_query) if app_query.lower() in w.title.lower()]
                if not wins: return f"Could not find window matching '{app_query}'."
                win = wins[0]
                
                if operation == "window_focus":
                    win.restore()
                    win.activate()
                    return f"Focused '{win.title}'."
                
                if operation == "window_minimize":
                    win.minimize()
                    return f"Minimized '{win.title}'."
                
                if operation == "window_maximize":
                    win.maximize()
                    return f"Maximized '{win.title}'."
                
                if operation == "window_close":
                    win.close()
                    return f"Closed '{win.title}'."
                
                if operation == "window_snap_left":
                    win.restore()
                    win.activate()
                    time.sleep(0.2)
                    pyautogui.hotkey("win", "left")
                    return f"Snapped '{win.title}' left."
                
                if operation == "window_snap_right":
                    win.restore()
                    win.activate()
                    time.sleep(0.2)
                    pyautogui.hotkey("win", "right")
                    return f"Snapped '{win.title}' right."

            return f"Unknown computer operation: {operation}"

        except Exception as e:
            logger.error(f"[COMPUTER] {e}")
            return f"Action failed: {str(e)[:150]}"
