"""WhatsApp plugin — send text messages and files via WhatsApp Desktop.

Patches (v4):
  FIX-A  time.sleep(1.0) after os.startfile() before polling window.
  FIX-B  Ctrl+F focus delay 1.0s; typing interval 0.07.
  FIX-C  Absolute path guard.
  FIX-D  Window activation retry loop (3 attempts).
  FIX-E  Post-paste sleep 2.5s for file sends.
  FIX-F  Downloads fallback search by filename.
  FIX-G  (NEW) Username-agnostic resolution: the brain often constructs paths
         with a wrong/cached username (e.g. C:\\Users\\Boss\\...). We now extract
         just the filename from whatever path the brain provides and resolve the
         real directory via USERPROFILE / registry — never trusting the
         brain-supplied username component.
"""

import os
import subprocess
import time
from pathlib import Path
from backend.plugins._base import Plugin
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def _get_downloads_path() -> Path:
    """Resolve real Downloads folder via Windows registry — no username assumed."""
    import winreg
    try:
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            reg_path, _ = winreg.QueryValueEx(key, "{374DE290-123F-4565-9164-39C4925E467B}")
            return Path(os.path.expandvars(reg_path)).resolve()
    except Exception:
        home = Path(os.environ.get("USERPROFILE") or os.path.expanduser("~"))
        for candidate in [home / "Downloads", home / "OneDrive" / "Downloads"]:
            if candidate.exists():
                return candidate.resolve()
        return (home / "Downloads").resolve()


class WhatsAppPlugin(Plugin):
    name = "send_whatsapp"
    description = "Send WhatsApp text or files to a contact."
    parameters = {
        "operation": {"type": "string", "enum": ["text", "file"], "required": True},
        "contact":   {"type": "string", "description": "Contact name", "required": True},
        "message":   {"type": "string", "description": "Message text"},
        "file_path": {"type": "string", "description": "Full absolute path to file or files. Use a comma-separated list for sending multiple files at once."}
    }

    def _wait_for_window(self, title_substring: str = "WhatsApp", timeout: int = 20) -> bool:
        try:
            import pygetwindow as gw
            start = time.time()
            while time.time() - start < timeout:
                windows = [w for w in gw.getAllWindows()
                           if title_substring.lower() in w.title.lower()]
                if windows:
                    win = windows[0]
                    for _ in range(3):
                        try:
                            win.activate()
                            break
                        except Exception:
                            time.sleep(0.2)
                    time.sleep(0.5)
                    return True
                time.sleep(1)
            return False
        except ImportError:
            time.sleep(4)
            return True

    def _clipboard_has_file(self) -> bool:
        check = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "Try { [System.Windows.Forms.Clipboard]::ContainsFileDropList() } "
            "Catch { $false }"
        )
        res = subprocess.run(
            ["powershell", "-WindowStyle", "Hidden", "-Command", check],
            capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return "True" in res.stdout

    def _resolve_file_path(self, file_path: str) -> tuple:
        """
        FIX-G: Username-agnostic resolution.

        The brain frequently constructs paths like C:\\Users\\<wrong_name>\\Downloads\\file.
        We ignore the directory component entirely and resolve the real Downloads
        path from USERPROFILE / registry, then search for the filename there.

        Resolution order:
          1. Exact path as given (covers cases where path is actually correct).
          2. Same filename inside the real Downloads folder.
          3. Fuzzy stem match inside Downloads (most recently modified wins).
          4. Error with actionable message.

        Supports comma-separated strings for multiple files.
        """
        if not file_path:
            return [], "No file path provided."

        # Handle multiple files
        raw_paths = []
        if "," in file_path:
            raw_paths = [p.strip() for p in file_path.split(",")]
        else:
            raw_paths = [file_path.strip()]

        resolved_paths = []
        errors = []

        for rp in raw_paths:
            p = Path(rp)
            filename = p.name

            # 1. Try exact path
            if p.is_absolute() and p.resolve().exists():
                logger.debug(f"[WHATSAPP] Exact path OK: {p.resolve()}")
                resolved_paths.append(str(p.resolve()))
                continue

            # 2. Downloads lookup
            downloads = _get_downloads_path()
            candidate = downloads / filename
            if candidate.exists():
                logger.debug(f"[WHATSAPP] Found in Downloads: {candidate}")
                resolved_paths.append(str(candidate))
                continue

            # 3. Fuzzy match
            matches = sorted(
                downloads.glob(f"*{Path(filename).stem}*"),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            if matches:
                logger.debug(f"[WHATSAPP] Fuzzy match: {matches[0]}")
                resolved_paths.append(str(matches[0]))
                continue

            errors.append(f"Could not find '{filename}'")

        if errors:
            return [], " | ".join(errors)

        return resolved_paths, None

    def execute(self, operation: str = "text", contact: str = "",
                message: str = "", file_path: str = "", **_) -> str:

        if not contact:
            return "Need a contact name."

        try:
            import pyautogui
            import pyperclip

            if operation == "file":
                resolved_list, err = self._resolve_file_path(file_path)
                if err:
                    return err
                
                # Multi-file PowerShell script
                # We build the string collection in a loop
                paths_ps = ""
                for p in resolved_list:
                    # Escape single quotes for PowerShell
                    safe_p = p.replace("'", "''")
                    paths_ps += f"$col.Add('{safe_p}'); "

                ps_script = (
                    "Add-Type -AssemblyName System.Windows.Forms; "
                    "$col = New-Object System.Collections.Specialized.StringCollection; "
                    f"{paths_ps}"
                    "[System.Windows.Forms.Clipboard]::SetFileDropList($col)"
                )
                subprocess.run(
                    ["powershell", "-WindowStyle", "Hidden", "-Command", ps_script],
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )

                if not self._clipboard_has_file():
                    return "System clipboard failed to lock file handle. Please retry."

            # FIX-A
            os.startfile("whatsapp://")
            time.sleep(1.0)

            if not self._wait_for_window("WhatsApp"):
                return "WhatsApp window not detected. Is WhatsApp Desktop installed?"

            # FIX-B
            pyautogui.hotkey("ctrl", "f")
            time.sleep(1.0)
            pyautogui.write(contact, interval=0.07)
            time.sleep(1.5)
            pyautogui.press("enter")
            time.sleep(1.2)

            if operation == "text":
                pyperclip.copy(message)
                pyautogui.hotkey("ctrl", "v")
                time.sleep(0.5)
                pyautogui.press("enter")
                logger.info(f"[WHATSAPP] Text sequence finished for {contact}.")
                return (
                    f"Sequence completed. Please verify the message was sent "
                    f"to {contact} in WhatsApp."
                )

            else:
                if not self._clipboard_has_file():
                    return "Clipboard was cleared by another process. File send aborted."

                pyautogui.hotkey("ctrl", "v")
                time.sleep(2.5)   # FIX-E
                pyautogui.press("enter")
                logger.info(f"[WHATSAPP] File sequence finished for {contact}.")
                return (
                    f"Sequence completed. I've sent the requested files to {contact} in WhatsApp."
                )

        except Exception as e:
            logger.error(f"[WHATSAPP] Automation failure: {e}")
            return f"WhatsApp automation sequence interrupted: {e}"