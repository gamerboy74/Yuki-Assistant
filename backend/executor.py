"""
Executor — performs OS and app actions based on the brain's JSON output.
Each action type resolves to a concrete Windows operation.
"""
import os
import subprocess
import time
import webbrowser
import datetime
from pathlib import Path
from typing import Optional, Union
from backend.utils.logger import get_logger
from backend import memory as mem

logger = get_logger(__name__)

def get_desktop_path() -> Path:
    """Robustly resolve the Windows Desktop path."""
    import winreg
    try:
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            reg_path, _ = winreg.QueryValueEx(key, "Desktop")
            return Path(os.path.expandvars(reg_path))
    except Exception:
        # Fallback to standard locations
        home = Path(os.path.expanduser("~"))
        for candidate in [home / "OneDrive" / "Desktop", home / "Desktop"]:
            if candidate.exists():
                return candidate
        return home / "Desktop"

def get_user_folder(folder_name: str) -> Path:
    """Resolve standard user folders (Desktop, Downloads, Documents) robustly, handling OneDrive."""
    import winreg
    try:
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
        reg_names = {
            "Desktop": "Desktop",
            "Downloads": "{374DE290-123F-4565-9164-39C4925E467B}",
            "Documents": "Personal"
        }
        reg_name = reg_names.get(folder_name, folder_name)
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            reg_path, _ = winreg.QueryValueEx(key, reg_name)
            return Path(os.path.expandvars(reg_path))
    except Exception:
        home = Path(os.path.expanduser("~"))
        for candidate in [home / "OneDrive" / folder_name, home / folder_name]:
            if candidate.exists():
                return candidate
        return home / folder_name

# Map of friendly app names to executable commands
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
    # Messaging / comms
    "whatsapp":         "whatsapp",
    "whats app":        "whatsapp",
    "telegram":         "telegram",
    "zoom":             "zoom",
    "teams":            "msteams",
    "microsoft teams":  "msteams",
    "slack":            "slack",
    # Media
    "photos":           "ms-photos:",
    "camera":           "microsoft.windows.camera:",
    "paint":            "mspaint",
    "3d paint":         "ms-paint:",
}

# Map of app names to process names for killing
KILL_MAP = {
    "chrome":       "chrome.exe",
    "google chrome": "chrome.exe",
    "firefox":      "firefox.exe",
    "edge":         "msedge.exe",
    "microsoft edge": "msedge.exe",
    "notepad":      "notepad.exe",
    "spotify":      "Spotify.exe",
    "discord":      "Discord.exe",
    "vlc":          "vlc.exe",
    "vs code":      "Code.exe",
    "vscode":       "Code.exe",
    "word":         "WINWORD.EXE",
    "excel":        "EXCEL.EXE",
    "powerpoint":   "POWERPNT.EXE",
    "whatsapp":     "WhatsApp.exe",
    "telegram":     "Telegram.exe",
    "zoom":         "Zoom.exe",
    "teams":        "Teams.exe",
    "slack":        "slack.exe",
    "calculator":   "CalculatorApp.exe",
    "calc":         "CalculatorApp.exe",
}


def execute(action: dict) -> Union[str, dict, None]:
    """
    Execute an action returned by the brain.
    Returns an optional override response string, or None.

    action format: {"type": "action_name", "params": {...}}
    """
    atype = action.get("type", "none")
    params = action.get("params", {})

    logger.info(f"Executing: {atype} | params: {params}")

    if atype != "none":
        import json
        try:
            print(json.dumps({"type": "loading", "text": f"RUNNING {atype.upper().replace('_', ' ')}..."}), flush=True)
        except Exception:
            pass

    try:
        if atype == "open_app":
            return _open_app(params)
        elif atype == "close_app":
            return _close_app(params)
        elif atype == "type_text":
            return _type_text(params)
        elif atype == "search_web":
            return _search_web(params)
        elif atype == "open_url":
            return _open_url(params)
        elif atype == "send_whatsapp":
            return _send_whatsapp(params)
        elif atype == "send_whatsapp_file":
            return _send_whatsapp_file(params)
        elif atype == "play_youtube":
            return _play_youtube(params)
        elif atype == "play_spotify":
            return _play_spotify(params)
        elif atype == "file_op":
            return _file_op(params)
        elif atype == "system_info":
            return _system_info(params)
        elif atype == "screenshot":
            return _screenshot()
        # ── New Gemma 3 4B actions ──────────────────────────────────────────
        elif atype == "set_volume":
            return _set_volume(params)
        elif atype == "set_brightness":
            return _set_brightness(params)
        elif atype == "get_weather":
            return _get_weather(params)
        elif atype == "system_control":
            return _system_control(params)
        elif atype == "clipboard_copy":
            return _clipboard_copy(params)
        elif atype == "reminder":
            return _reminder(params)
        elif atype == "media_controls":
            return _media_controls(params)
        elif atype == "smart_navigate":
            return _smart_navigate(params)
        elif atype == "get_user_info":
            return _get_user_info(params)
        elif atype == "write_file":
            return _write_file(params)
        elif atype == "design_web_page":
            return _design_web_page(params)
        # ───────────────────────────────────────────────────────────────────
        elif atype == "none":
            return None  # Pure conversation — no OS action needed
        else:
            logger.warning(f"Unknown action type: {atype}")
            return None
    except Exception as e:
        logger.error(f"Executor error ({atype}): {e}")
        return f"I ran into an error: {str(e)[:100]}"


def _open_app(params: dict) -> None:
    name = params.get("name", "").lower().strip()
    exe = APP_MAP.get(name, name)  # Use map or pass through as-is

    # Direct Windows protocol support
    if "whatsapp" in name:
        os.startfile("whatsapp://")
    elif "zoom" in name:
        os.startfile("zoommtg://")
    elif "spotify" in name:
        os.startfile("spotify:")
    elif "ms-settings:" in exe or "ms-photos:" in exe or ":" in exe:
        os.startfile(exe)
    elif exe == "explorer" and params.get("path"):
        subprocess.Popen(["explorer", params["path"]])
    else:
        try:
            subprocess.Popen(["start", "", exe], shell=True)
        except Exception:
            subprocess.Popen(exe, shell=True)
    return None


def _close_app(params: dict) -> str:
    name = params.get("name", "").lower().strip()
    
    if name in ["active", "this", "window", "current"]:
        try:
            import pyautogui
            pyautogui.hotkey("alt", "f4")
            return "Closed the active window."
        except Exception:
            # PowerShell fallback to close active window
            script = "(New-Object -ComObject WScript.Shell).SendKeys('%{F4}')"
            subprocess.Popen(["powershell", "-WindowStyle", "Hidden", "-Command", script],
                             creationflags=subprocess.CREATE_NO_WINDOW)
            return "Attempted to close the active window."

    proc = KILL_MAP.get(name, f"{name}.exe")
    try:
        # Check if process is running first (optional but cleaner)
        # Using /t for tree kill (closes child processes like chrome tabs/windows)
        subprocess.Popen(["taskkill", "/f", "/t", "/im", proc], shell=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Closed {name}."
    except Exception as e:
        logger.error(f"Close app error: {e}")
        return f"Couldn't close {name}."


def _type_text(params: dict) -> None:
    text = params.get("text", "")
    try:
        import pyautogui
        time.sleep(0.5)  # Allow window focus
        pyautogui.typewrite(text, interval=0.02)
    except ImportError:
        logger.warning("pyautogui not installed — cannot type text")
    return None


def _search_web(params: dict) -> None:
    query = params.get("query", "")
    url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
    webbrowser.open(url)
    return None


def _open_url(params: dict) -> None:
    url = params.get("url", "")
    if url:
        webbrowser.open(url)
    return None


def _send_whatsapp(params: dict) -> Union[str, dict, None]:
    contact = params.get("contact", "")
    message = params.get("message", "")

    if not contact or not message:
        return "Please tell me the contact name and message."

    try:
        import pyautogui
        
        # 1. Open the WhatsApp Desktop application via URI
        os.startfile("whatsapp://")
        time.sleep(3.5) # Wait for app to launch and focus
        
        # 2. Trigger Search (Ctrl + F)
        pyautogui.hotkey("ctrl", "f")
        time.sleep(0.5)
        
        # 3. Search for contact
        pyautogui.typewrite(contact, interval=0.05)
        time.sleep(1.5) # Wait for list to filter
        
        # 4. Select the top result chat
        pyautogui.press("enter")
        time.sleep(1.0)
        
        # 5. Type and send the message
        pyautogui.typewrite(message, interval=0.02)
        pyautogui.press("enter")

        return {
            "speak": f"Maine {contact} ko message bhej diya hai.",
            "ui_log": f"Sent '{message}' to '{contact}' via native WhatsApp Desktop."
        }

    except ImportError:
        logger.warning("pyautogui not installed — opening WhatsApp manually")
        os.startfile("whatsapp://")
        return {
            "speak": "Maine WhatsApp open kar diya hai, please send manually.",
            "ui_log": f"⚠️ Missing 'pyautogui' dependency.\nOpened WhatsApp Desktop. Please send your message to '{contact}' manually."
        }
    except Exception as e:
        logger.error(f"WhatsApp error: {e}")
        return {
            "speak": "Yeh message type karne mein thodi problem aa rahi hai.",
            "ui_log": f"⚠️ WhatsApp Desktop Automation Error:\n{str(e)[:150]}"
        }

def _send_whatsapp_file(params: dict) -> Union[str, dict, None]:
    contact   = params.get("contact", "")
    file_name = params.get("file_name", "")
    file_path = params.get("file_path", "")

    if not contact:
        return "Please tell me who you want to send the file to."

    # ── 1. Resolve file path robustly ─────────────────────────────────────────
    if not file_path or not os.path.isfile(file_path):
        search_terms = file_name.lower().strip().split()
        if not search_terms:
            return "What file should I send?"

        search_dirs = [
            get_user_folder("Downloads"),
            get_user_folder("Desktop"),
            get_user_folder("Documents")
        ]
        
        found_file = None
        for folder in search_dirs:
            if not folder.exists(): continue
            for f in folder.iterdir():
                if f.is_file():
                    fname_lower = f.name.lower()
                    # Match if ALL search terms are present in filename
                    if all(term in fname_lower for term in search_terms):
                        found_file = f
                        break
            if found_file: break
        
        if found_file:
            file_path = str(found_file)

    if not file_path or not os.path.isfile(file_path):
        return {
            "speak": f"Mujhe '{file_name}' naam ki koi file nahi mili.",
            "ui_log": f"⚠️ File not found: '{file_name}' (Searched Downloads/Desktop/Documents)"
        }

    try:
        import pyautogui
        logger.info(f"Preparing to send file: {file_path}")

        # ── 2. Copy file to Windows clipboard (FileDropList format) ───────────
        # This allows Ctrl+V to work as a 'file attachment' in WhatsApp
        normalized_path = os.path.abspath(file_path).replace("'", "''") # Escape for PowerShell
        ps_script = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$col = New-Object System.Collections.Specialized.StringCollection; "
            f"$col.Add('{normalized_path}'); "
            "[System.Windows.Forms.Clipboard]::SetFileDropList($col)"
        )
        subprocess.run(
            ["powershell", "-WindowStyle", "Hidden", "-Command", ps_script],
            creationflags=subprocess.CREATE_NO_WINDOW,
            check=True
        )
        time.sleep(0.5)

        # ── 3. Open WhatsApp and search for contact ───────────────────────────
        os.startfile("whatsapp://")
        time.sleep(4.0) # Wait for app focus
        
        # Ensure we are in search (native WhatsApp shortcut)
        pyautogui.hotkey("ctrl", "f")
        time.sleep(0.5)
        # Type contact name (typed slowly to ensure search picks it up)
        pyautogui.typewrite(contact, interval=0.05)
        time.sleep(1.5)
        pyautogui.press("enter")
        time.sleep(1.5)

        # ── 4. Paste and Send ─────────────────────────────────────────────────
        # Paste trigger (shows the preview window in WhatsApp)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(2.5) # Wait for WhatsApp to process the file and show the send button
        
        # Press Enter twice (once for the preview caption, once to send)
        pyautogui.press("enter")
        time.sleep(0.5)
        pyautogui.press("enter")

        return {
            "speak": f"Theek hai, maine {contact} ko file bhej di hai.",
            "ui_log": f"✅ Successfully sent file:\n{os.path.basename(file_path)} ➔ {contact}"
        }

    except Exception as e:
        logger.error(f"WhatsApp file error: {e}")
        return {
            "speak": "File bhejne mein problem aa rahi hai. Kya WhatsApp open hai?",
            "ui_log": f"⚠️ WhatsApp File Error:\n{str(e)[:150]}"
        }



def _play_youtube(params: dict) -> None:
    query = params.get("query", "")
    auto_play = params.get("auto_play", True)
    
    import urllib.request
    import urllib.parse
    import re
    
    try:
        # Fetch youtube search HTML
        encoded = urllib.parse.quote(query)
        url = f"https://www.youtube.com/results?search_query={encoded}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        html = urllib.request.urlopen(req, timeout=5).read().decode('utf-8')
        
        # Find the first video ID
        video_ids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)
        if video_ids and auto_play:
            unique_ids = list(dict.fromkeys(video_ids))
            # Append &list=RD{video_id} to trigger a YouTube Mix (Radio)
            video_url = f"https://www.youtube.com/watch?v={unique_ids[0]}&list=RD{unique_ids[0]}"
            webbrowser.open(video_url)
            return None
    except Exception as e:
        logger.debug(f"Youtube auto-play scrape failed: {e}")
        
    url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
    webbrowser.open(url)
    return None


def _play_spotify(params: dict) -> Union[str, dict]:
    query = params.get("query", "")
    if query:
        import urllib.request
        import urllib.parse
        import re
        import threading
        
        encoded = urllib.parse.quote(query)
        track_uri = None
        
        # Strategy A: Find exact Track URI (Highly reliable playback context)
        try:
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote('site:open.spotify.com/track ' + query)}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            html = urllib.request.urlopen(req, timeout=5).read().decode('utf-8')
            m = re.search(r'open\.spotify\.com/track/([a-zA-Z0-9]{22})', html)
            if m:
                track_uri = f"spotify:track:{m.group(1)}"
        except Exception as e:
            logger.debug(f"Spotify scrape failed: {e}")

        if track_uri:
            try:
                # Modern Spotify desktop usually auto-plays track URIs. 
                os.startfile(track_uri)
                return f"Playing {query} on Spotify."
            except Exception as e:
                logger.debug(f"Direct play failed, falling back: {e}")

        # Strategy B: Fallback to general Search UI
        try:
            os.startfile(f"spotify:search:{encoded}")
            def _auto_play_search():
                time.sleep(3.5)
                script = (
                    "$wshell = New-Object -ComObject wscript.shell; "
                    "$proc = Get-Process -Name 'Spotify' -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1; "
                    "if ($proc) { "
                    "  $wshell.AppActivate($proc.Id); Start-Sleep -m 500; "
                    "  $wshell.SendKeys('{TAB}'); Start-Sleep -m 100; "
                    "  $wshell.SendKeys('{TAB}'); Start-Sleep -m 100; "
                    "  $wshell.SendKeys('{ENTER}'); "
                    "}"
                )
                subprocess.Popen(["powershell", "-WindowStyle", "Hidden", "-Command", script], creationflags=subprocess.CREATE_NO_WINDOW)
            
            threading.Thread(target=_auto_play_search, daemon=True).start()
            return f"Searching for {query} on Spotify."
        except Exception as e:
            logger.error(f"Spotify startfile error: {e}")
            return {
                "speak": "Sorry, main abhi Spotify open nahi kar paayi.",
                "ui_log": f"⚠️ Spotify Launch Error:\n{str(e)[:150]}"
            }
    else:
        try:
            os.startfile("spotify:")
        except Exception:
            pass
        return "Opening Spotify."


def _write_file(params: dict) -> str:
    """Write or append content to a file. Auto-creates the 'Yuki_Designs' folder on Desktop if needed."""
    path_str = params.get("path", "")
    content  = params.get("content", "")
    mode     = params.get("mode", "overwrite") # overwrite or append
    
    if not path_str:
        # Use our robust desktop resolver
        desktop = get_desktop_path() / "Yuki_Designs"
        desktop.mkdir(parents=True, exist_ok=True)
        path = desktop / f"design_{int(time.time())}.html"
    else:
        path = Path(path_str).resolve()
        
    try:
        # Safety check: restrict to user profile
        user_home = Path(os.path.expanduser("~")).resolve()
        if user_home not in path.parents and path != user_home:
            return f"Access denied: '{path}' is outside your home directory."

        # Ensure directory exists
        path.parent.mkdir(parents=True, exist_ok=True)
        
        write_mode = "w" if mode == "overwrite" else "a"
        with open(path, write_mode, encoding="utf-8") as f:
            f.write(content)
            
        logger.info(f"[EXECUTOR] File written to {path}")
        
        # Auto-view if it's a web page
        if path.suffix in [".html", ".htm"]:
            import webbrowser
            webbrowser.open(f"file:///{path}")
            return f"Design complete! I've saved it to your Desktop and opened it in your browser."

        return f"Successfully wrote to {path.name}."
    except Exception as e:
        logger.error(f"Write file error: {e}")
        return f"failed to write file: {e}"

def _design_web_page(params: dict) -> str:
    """High-level wrapper for web design. Hands off content to _write_file."""
    return _write_file(params)


def _file_op(params: dict) -> Optional[str]:
    import shutil

    operation = params.get("operation", "")
    source    = params.get("source", "")
    dest      = params.get("dest", "")
    pattern   = params.get("pattern", None)

    # ── Safety: restrict all paths to the user's home directory ──────────────
    user_home = Path(os.path.expanduser("~")).resolve()

    def _safe(path_str: str) -> Path:
        """Resolve path and verify it is under %USERPROFILE%."""
        if not path_str:
            raise ValueError("Empty path provided")
        p = Path(path_str).resolve()
        if user_home not in p.parents and p != user_home:
            raise PermissionError(
                f"Access denied: path '{p}' is outside your home directory."
            )
        return p

    try:
        src = _safe(source) if source else None
        dst = _safe(dest)   if dest   else None
    except (ValueError, PermissionError) as e:
        logger.error(f"File op safety check failed: {e}")
        return str(e)

    try:
        if operation == "copy":
            shutil.copy2(str(src), str(dst))
        elif operation == "move":
            shutil.move(str(src), str(dst))
        elif operation == "delete":
            if src is None:
                return "No source path specified for delete."
            if src.is_dir():
                # Block recursive directory deletion — too dangerous
                return (
                    f"I won't delete the folder '{src.name}' automatically. "
                    "Please delete it manually in File Explorer."
                )
            if src.is_file():
                src.unlink()
            else:
                return f"File not found: {src}"
        elif operation == "move_pattern" and pattern:
            import glob
            safe_src_dir = _safe(source)
            for f in glob.glob(os.path.join(str(safe_src_dir), pattern)):
                shutil.move(f, str(dst))
        else:
            return f"Unknown file operation: {operation}"
    except PermissionError as e:
        logger.error(f"File op permission error: {e}")
        return f"Permission denied: {e}"
    except Exception as e:
        logger.error(f"File op error: {e}")
        return f"File operation failed: {str(e)[:100]}"

    return None


def _system_info(params: dict) -> str:
    """Return system information as a string for Yuki to speak."""
    query = params.get("query", "time").lower()

    now = datetime.datetime.now()

    if "time" in query:
        return f"The current time is {now.strftime('%I:%M %p')}."
    elif "date" in query:
        return f"Today is {now.strftime('%A, %B %d, %Y')}."
    elif "battery" in query:
        try:
            import psutil
            battery = psutil.sensors_battery()
            if battery:
                pct = int(battery.percent)
                charging = "and charging" if battery.power_plugged else ""
                return f"Battery is at {pct}% {charging}."
        except Exception:
            pass
        return "I couldn't read the battery status."
    elif "cpu" in query:
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=1)
            return f"CPU usage is {cpu}%."
        except Exception:
            return "Unable to get CPU info."
    elif "ram" in query or "memory" in query:
        try:
            import psutil
            mem = psutil.virtual_memory()
            used_gb = mem.used / (1024 ** 3)
            total_gb = mem.total / (1024 ** 3)
            return f"You're using {used_gb:.1f} GB of {total_gb:.1f} GB RAM."
        except Exception:
            return "Unable to get memory info."
    else:
        return f"The time is {now.strftime('%I:%M %p')} on {now.strftime('%A, %B %d')}."


def _screenshot() -> str:
    try:
        import pyautogui
        filename = f"screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        desktop = os.path.join(os.path.expanduser("~"), "Desktop", filename)
        pyautogui.screenshot(desktop)
        return f"Screenshot saved to your Desktop as {filename}."
    except ImportError:
        return "pyautogui is not installed — cannot take screenshot."
    except Exception as e:
        return f"Screenshot failed: {e}"


# ── New actions (Gemma 3 4B extended capabilities) ────────────────────────────

def _set_volume(params: dict) -> str:
    """Set Windows system volume (0-100). Handles __up10/__down10 step tokens."""
    raw = params.get("level", 50)

    # Step tokens from intent_router ("volume up" / "volume down")
    if raw == "__up10" or raw == "__down10":
        step = 10 if raw == "__up10" else -10
        try:
            import ctypes
            # Get current volume via pycaw if available, else just send key presses
            key = chr(175) if step > 0 else chr(174)   # VK_VOLUME_UP / VK_VOLUME_DOWN
            presses = abs(step) // 2                    # each key press ≈ 2 units
            shell = __import__("win32com.client", fromlist=["Dispatch"]).Dispatch("WScript.Shell")
            for _ in range(max(1, presses)):
                shell.SendKeys(key)
            direction = "up" if step > 0 else "down"
            return f"Volume turned {direction}."
        except Exception:
            # PowerShell fallback
            keys = "[char]175" if step > 0 else "[char]174"
            presses = abs(step) // 2
            script = f"$s=New-Object -ComObject WScript.Shell; for($i=0;$i -lt {presses};$i++){{$s.SendKeys({keys})}}"
            subprocess.Popen(["powershell", "-WindowStyle", "Hidden", "-Command", script],
                             creationflags=subprocess.CREATE_NO_WINDOW)
            direction = "up" if step > 0 else "down"
            return f"Volume turned {direction}."

    level = max(0, min(100, int(raw)))
    try:
        # Use nircmd if available (lightweight, no pip install needed)
        result = subprocess.run(
            ["nircmd", "setsysvolume", str(int(level * 655.35))],
            capture_output=True
        )
        if result.returncode == 0:
            return f"Volume set to {level}%."
    except FileNotFoundError:
        pass
    try:
        # PowerShell fallback (always available on Windows)
        script = (
            f"$obj = New-Object -ComObject WScript.Shell; "
            f"$vol = [int]({level}/2); "
            f"for ($i=0; $i -lt 50; $i++) {{ $obj.SendKeys([char]174) }}; "
            f"for ($i=0; $i -lt $vol; $i++) {{ $obj.SendKeys([char]175) }}"
        )
        subprocess.Popen(
            ["powershell", "-WindowStyle", "Hidden", "-Command", script],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return f"Volume adjusted to approximately {level}%."
    except Exception as e:
        logger.error(f"set_volume error: {e}")
        return "I couldn't adjust the volume on this system."


def _set_brightness(params: dict) -> str:
    """Set screen brightness (0-100) via WMI."""
    level = max(0, min(100, int(params.get("level", 70))))
    try:
        script = (
            f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{level})"
        )
        subprocess.Popen(
            ["powershell", "-WindowStyle", "Hidden", "-Command", script],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return f"Brightness set to {level}%."
    except Exception as e:
        logger.error(f"set_brightness error: {e}")
        return "I couldn't change the brightness. Make sure you're on a laptop with a WMI-compatible display."




def _detect_audio_app() -> tuple[str | None, int | None]:
    """
    Detect which process is currently producing audio using the Windows
    Core Audio API (pycaw).
    Returns (process_name, pid) or (None, None) if not found.
    
    Priority order: Spotify > Chrome/YouTube > any other audio process.
    """
    PRIORITY_APPS = ["Spotify", "chrome", "msedge", "firefox", "vlc", "groove"]
    
    try:
        from pycaw.pycaw import AudioUtilities
        import psutil
        
        sessions = AudioUtilities.GetAllSessions()
        candidates: list[tuple[int, str, int]] = []  # (priority, name, pid)
        
        for session in sessions:
            if session.Process is None:
                continue
            pid = session.Process.Id
            try:
                proc = psutil.Process(pid)
                proc_name = proc.name()  # e.g. "Spotify.exe", "chrome.exe"
                base = proc_name.lower().replace(".exe", "")
                
                # Check if this process has an active audio state
                # SimpleAudioVolume.GetMute() being False is a weak signal;
                # instead we enumerate session state
                try:
                    state = session.State  # 0=inactive, 1=active, 2=expired
                    if state != 1:
                        continue
                except Exception:
                    pass
                
                # Assign a priority score
                priority = 99
                for i, app in enumerate(PRIORITY_APPS):
                    if app.lower() in base:
                        priority = i
                        break
                
                candidates.append((priority, proc_name, pid))
                logger.debug(f"[AUDIO DETECT] Active audio: {proc_name} (pid={pid}, priority={priority})")
                
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        if candidates:
            candidates.sort(key=lambda x: x[0])
            _, proc_name, pid = candidates[0]
            return proc_name, pid
            
    except Exception as e:
        logger.debug(f"[AUDIO DETECT] pycaw detection failed: {e}")
    
    return None, None


def _focus_and_press(pid: int, key: str) -> bool:
    """
    Flash-focus the window of the given PID, press the key, then restore.
    Returns True if successful.
    """
    # Map pyautogui key name to character codes for wscript.shell SendKeys
    # VK_MEDIA_NEXT_TRACK = 176, VK_MEDIA_PREV_TRACK = 177, VK_MEDIA_PLAY_PAUSE = 179
    key_code = {
        "playpause": "[char]179",
        "nexttrack": "[char]176",
        "prevtrack": "[char]177",
    }.get(key, "[char]179")
    
    try:
        script = (
            f"$wshell = New-Object -ComObject wscript.shell; "
            f"$proc = Get-Process -Id {pid} -ErrorAction SilentlyContinue; "
            f"if ($proc) {{ "
            f"  $wshell.AppActivate($proc.Id); "
            f"  Start-Sleep -Milliseconds 400; "
            f"  $wshell.SendKeys({key_code}); "
            f"  Write-Output 'ok' "
            f"}}"
        )
        result = subprocess.run(
            ["powershell", "-WindowStyle", "Hidden", "-Command", script],
            capture_output=True, text=True, timeout=3,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if "ok" in result.stdout:
            return True
    except Exception as e:
        logger.debug(f"[FOCUS PRESS] failed: {e}")
    return False


def _media_controls(params: dict) -> str:
    """
    Smart media controls:
    1. Detect which app is currently producing audio via Windows Core Audio API.
    2. Briefly focus that app's window and send the correct media keystroke.
    3. Falls back to global pyautogui media keys if no active audio app found.
    """
    action = params.get("action", "playpause")
    
    key_map = {
        "playpause": "playpause",
        "next":      "nexttrack",
        "previous":  "prevtrack",
    }
    pyautogui_key = key_map.get(action, "playpause")
    
    action_desc = {
        "playpause": "Playing/Pausing",
        "next":      "Skipping to next track",
        "previous":  "Going to previous track",
    }.get(action, "Controlling")
    
    # ── Step 1: Detect which app is playing audio ──────────────────────────
    proc_name, pid = _detect_audio_app()
    
    if pid:
        logger.info(f"[MEDIA] Detected audio app: {proc_name} (pid={pid}), action={action}")
        success = _focus_and_press(pid, pyautogui_key)
        if success:
            return f"{action_desc} on {proc_name.replace('.exe', '')}."
    
    # ── Step 2: Fallback — global OS media key ─────────────────────────────
    logger.info(f"[MEDIA] No active audio app detected, using global media key: {pyautogui_key}")
    try:
        import pyautogui
        pyautogui.press(pyautogui_key)
        return f"{action_desc}."
    except Exception as e:
        logger.error(f"[MEDIA] Global key failed: {e}")
        return "Couldn't control media playback."


def _clipboard_copy(params: dict) -> str:
    """Copy text to the Windows clipboard."""
    text = params.get("text", "")
    if not text:
        return "No text provided to copy."
    try:
        # PowerShell: always available on Windows, no extra library needed
        ps_text = text.replace('"', '`"')
        subprocess.run(
            ["powershell", "-Command", f'Set-Clipboard "{ps_text}"'],
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        preview = text[:40] + ("..." if len(text) > 40 else "")
        return f'Copied to clipboard: "{preview}"'
    except Exception as e:
        logger.error(f"clipboard_copy error: {e}")
        return "Couldn't copy to clipboard."


def _get_weather(params: dict) -> str:
    """Fetch current weather for a location. Auto-detects local city if none provided."""
    import requests
    # Support 'city', 'location', or 'target' keys
    location = params.get("location") or params.get("city") or params.get("target")
    location = str(location).strip() if (location and str(location).strip()) else ""
    
    lat, lon, display_name = None, None, None

    try:
        # 1. If no location provided, try auto-detection via IP
        if not location:
            user = mem.get_user()
            stored_loc = user.get("location", "").strip()
            
            if stored_loc:
                location = stored_loc
            else:
                try:
                    ip_url = "http://ip-api.com/json/"
                    ip_data = requests.get(ip_url, timeout=2).json()
                    if ip_data.get("status") == "success":
                        lat = ip_data.get("lat")
                        lon = ip_data.get("lon")
                        display_name = f"{ip_data.get('city')}, {ip_data.get('country')}"
                        logger.info(f"[WEATHER] Auto-detected: {display_name}")
                except Exception as e:
                    logger.debug(f"[WEATHER] Auto-detect failed: {e}")
                    location = "London" # Final fallback

        # 2. If we have a location name but no lat/lon yet, geocode it
        if location and not lat:
            # Use requests.utils.quote to handle spaces in city names
            geo_url = f"https://nominatim.openstreetmap.org/search?q={requests.utils.quote(location)}&format=json&limit=1"
            headers = {"User-Agent": "YukiAssistant/1.0"}
            geo_res = requests.get(geo_url, headers=headers, timeout=5).json()
            if not geo_res:
                return f"I couldn't find the location '{location}'."
            lat = geo_res[0]["lat"]
            lon = geo_res[0]["lon"]
            display_name = geo_res[0]["display_name"].split(",")[0]

        # 3. Fetch weather from Open-Meteo
        if lat and lon:
            w_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
            w_res = requests.get(w_url, timeout=5).json()
            cw = w_res.get("current_weather", {})
            temp = cw.get("temperature")
            wind = cw.get("windspeed")
            return f"Currently in {display_name}, it's {temp}°C with a wind speed of {wind} km/h."
        
        return "I'm having trouble fetching the weather right now."

    except Exception as e:
        logger.error(f"Weather tool error: {e}")
        return f"I couldn't fetch the weather: {str(e)[:100]}"

def _get_user_info(params: dict) -> str:
    """Retrieve personal information from local memory (Zero-Token)."""
    query = params.get("query", "").lower()
    user = mem.get_user()
    
    if "name" in query:
        return f"Your name is {user['name']}." if user['name'] else "I don't know your name yet."
    elif "preference" in query or "like" in query:
        prefs = user.get("preferences", {})
        if prefs:
            return "Here are the preferences I know: " + ", ".join(f"{k} is {v}" for k,v in prefs.items())
        return "I haven't recorded any specific preferences for you yet."
    
    return mem.context_block()

def _smart_navigate(params: dict) -> str:
    """Smart App Navigation using pywinauto (Local, Native UI Tree)."""
    try:
        from pywinauto import Desktop
        target = params.get("target", "").lower()
        action = params.get("action", "click") # click, focus, list
        
        # 1. Find the top-level window
        windows = Desktop(backend="uia").windows()
        active_win = None
        for w in windows:
            if w.is_active():
                active_win = w
                break
        
        if not active_win:
            return "No active window found to navigate."

        if action == "list":
            # List all buttons/interactables
            elems = active_win.descendants(control_type="Button")
            names = [e.window_text() for e in elems if e.window_text()]
            return "Found buttons: " + ", ".join(names[:10])

        # Find the specific element
        try:
            elem = active_win.child_window(title_re=f".*{target}.*", control_type="Button")
            if action == "click":
                elem.click_input()
                return f"Successfully clicked {target} in {active_win.window_text()}."
            elif action == "focus":
                elem.set_focus()
                return f"Focused on {target}."
        except Exception:
            return f"I couldn't find a button named '{target}' in the current window."

    except Exception as e:
        logger.error(f"Smart Navigate error: {e}")
        return f"Navigation failed: {str(e)[:100]}"

def _reminder(params: dict) -> str:
    """Add a persistent reminder to the local store (Zero-Token)."""
    text          = params.get("text", "Reminder!")
    delay_minutes = float(params.get("delay_minutes", 1))
    
    # Calculate due time
    due_dt = datetime.datetime.now() + datetime.timedelta(minutes=delay_minutes)
    due_iso = due_dt.isoformat()
    
    mem.add_reminder(text, due_iso)
    
    if delay_minutes < 1:
        when = f"{int(delay_minutes * 60)} seconds"
    else:
        when = f"{int(delay_minutes)} minutes"
        
    return f"Got it! I'll remind you about '{text}' in {when}."

def _system_control(params: dict) -> str:
    """Control Windows power states: shutdown, restart, sleep, lock."""
    from backend.utils.permissions import requires_explicit_confirmation, is_confirmed

    action = params.get("action", "").lower().strip()

    if requires_explicit_confirmation(action) and not is_confirmed(params):
        return f"Safety check: confirm {action} by retrying with confirm=true."
    
    try:
        if action == "shutdown":
            # 60s delay so user can cancel with 'shutdown /a' if mistake
            subprocess.Popen(["shutdown", "/s", "/t", "60", "/c", "Yuki is shutting down the system in 60 seconds..."])
            return "PC will shut down in 60 seconds. Say 'abort shutdown' to cancel."
        
        elif action == "restart":
            subprocess.Popen(["shutdown", "/r", "/t", "0"])
            return "Restarting the system now."
            
        elif action == "sleep":
            # Note: Hibernation must be off for this to actually sleep; otherwise it hibernates.
            # Powercfg -h off
            subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
            return "Putting the system to sleep."
            
        elif action == "lock":
            subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"])
            return "Locking the computer."
            
        elif action == "abort":
            subprocess.run(["shutdown", "/a"])
            return "Shutdown aborted."
            
        else:
            return f"Unknown system control action: {action}"
            
    except Exception as e:
        logger.error(f"System control error: {e}")
        return f"Failed to perform {action}: {e}"
