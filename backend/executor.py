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

logger = get_logger(__name__)

# Map of friendly app names to executable commands
APP_MAP = {
    "chrome":           "chrome",
    "google chrome":    "chrome",
    "firefox":          "firefox",
    "edge":             "msedge",
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
    "task manager":     "taskmgr",
    "file explorer":    "explorer",
    "explorer":         "explorer",
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
        elif atype == "clipboard_copy":
            return _clipboard_copy(params)
        elif atype == "reminder":
            return _reminder(params)
        elif atype == "media_controls":
            return _media_controls(params)
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
        return "Who should I send the file to?"

    # ── 1. Resolve file path ──────────────────────────────────────────────────
    if not file_path or not os.path.isfile(file_path):
        search_name = file_name.lower().strip()
        search_dirs = [
            os.path.join(os.path.expanduser("~"), "Downloads"),
            os.path.join(os.path.expanduser("~"), "Desktop"),
            os.path.join(os.path.expanduser("~"), "Documents"),
            # Also check OneDrive Downloads
            os.path.join(os.path.expanduser("~"), "OneDrive", "Downloads"),
        ]
        for folder in search_dirs:
            if not os.path.isdir(folder):
                continue
            for f in os.listdir(folder):
                if search_name and search_name in f.lower():
                    file_path = os.path.join(folder, f)
                    break
            if file_path and os.path.isfile(file_path):
                break

    if not file_path or not os.path.isfile(file_path):
        return {
            "speak": f"Yeh file mujhe nahi mili. Downloads mein check karein.",
            "ui_log": f"⚠️ File not found: '{file_name}' searched in Downloads/Desktop/Documents."
        }

    try:
        import pyautogui

        # ── 2. Copy file to Windows clipboard as a file object ────────────────
        # This is the KEY trick: SetFileDropList lets us Ctrl+V a file into WhatsApp
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

        # ── 3. Open WhatsApp Desktop and navigate to contact ──────────────────
        os.startfile("whatsapp://")
        time.sleep(3.5)

        pyautogui.hotkey("ctrl", "f")
        time.sleep(0.5)
        pyautogui.typewrite(contact, interval=0.05)
        time.sleep(1.5)
        pyautogui.press("enter")
        time.sleep(1.2)

        # ── 4. Paste the file into the chat (Ctrl+V) ──────────────────────────
        pyautogui.hotkey("ctrl", "v")
        time.sleep(2.0)   # WhatsApp processes the file drop and shows a preview

        # ── 5. Press Enter to send ────────────────────────────────────────────
        pyautogui.press("enter")
        time.sleep(0.8)

        fname = os.path.basename(file_path)
        return {
            "speak": f"Maine {contact} ko file bhej di.",
            "ui_log": f"✅ Sent '{fname}' to '{contact}' via WhatsApp Desktop."
        }

    except ImportError:
        return {
            "speak": "Automation tool nahi hai.",
            "ui_log": "⚠️ pyautogui not installed."
        }
    except Exception as e:
        logger.error(f"WhatsApp file send error: {e}")
        return {
            "speak": "File bhejne mein thodi mushkil aayi.",
            "ui_log": f"⚠️ WhatsApp file error: {str(e)[:150]}"
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

        try:
            if track_uri:
                # Open specific track
                os.startfile(track_uri)
                def _auto_play_track():
                    time.sleep(3.0) # Wait for page load
                    script = (
                        "$wshell = New-Object -ComObject wscript.shell; "
                        "$proc = Get-Process -Name 'Spotify' -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1; "
                        "if ($proc) { "
                        "  $wshell.AppActivate($proc.Id); Start-Sleep -m 500; "
                        "  $wshell.SendKeys('{ENTER}'); "
                        "}"
                    )
                    subprocess.Popen(["powershell", "-WindowStyle", "Hidden", "-Command", script], creationflags=subprocess.CREATE_NO_WINDOW)
                threading.Thread(target=_auto_play_track, daemon=True).start()
                return f"Playing {query} on Spotify."
            else:
                # Strategy B: Fallback to general Search UI
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
                return {
                    "speak": "Mujhe gaana toh mil gaya, par main Spotify pe play nahi kar paayi.",
                    "ui_log": f"⚠️ Could not resolve direct track URI for '{query}'.\nFell back to general Spotify search and attempted auto-play."
                }
                
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


def _get_weather(params: dict) -> str:
    """Fetch weather from wttr.in (free, no API key needed)."""
    import urllib.request
    import urllib.parse
    city = params.get("city", "")
    if not city:
        return "Which city's weather would you like to know?"
    try:
        encoded = urllib.parse.quote(city)
        url = f"http://wttr.in/{encoded}?format=3"
        req = urllib.request.Request(url, headers={"User-Agent": "curl/7.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            text = resp.read().decode("utf-8").strip()
        # wttr.in format=3 returns: "Delhi: ⛅  +32°C"
        return text if text else f"Couldn't get weather for {city}."
    except Exception as e:
        logger.error(f"get_weather error: {e}")
        return f"Couldn't fetch weather for {city} right now."


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


def _reminder(params: dict) -> str:
    """Show a Windows toast notification after a delay."""
    import threading
    text          = params.get("text", "Reminder!")
    delay_minutes = float(params.get("delay_minutes", 1))
    delay_secs    = delay_minutes * 60

    def _show_toast():
        time.sleep(delay_secs)
        try:
            ps_cmd = (
                f'[System.Reflection.Assembly]::LoadWithPartialName("System.Windows.Forms") | Out-Null; '
                f'$notify = New-Object System.Windows.Forms.NotifyIcon; '
                f'$notify.Icon = [System.Drawing.SystemIcons]::Information; '
                f'$notify.Visible = $true; '
                f'$notify.ShowBalloonTip(8000, "Yuki Reminder", "{text}", [System.Windows.Forms.ToolTipIcon]::Info); '
                f'Start-Sleep 10; $notify.Dispose()'
            )
            subprocess.Popen(
                ["powershell", "-WindowStyle", "Hidden", "-Command", ps_cmd],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except Exception as e:
            logger.error(f"Reminder toast error: {e}")

    t = threading.Timer(delay_secs, _show_toast)
    t.daemon = True
    t.start()

    if delay_minutes < 1:
        when = f"{int(delay_secs)}s"
    elif delay_minutes == 1:
        when = "1 minute"
    else:
        when = f"{int(delay_minutes)} minutes"
    return f"Got it! I'll remind you about '{text}' in {when}."
