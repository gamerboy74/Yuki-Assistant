"""
File Operations Plugin — read, write, and manage files safely.

Patches (v2):
  FIX-SAFE-1  _safe() now uses USERPROFILE env var as the primary home root
              instead of os.path.expanduser("~"), which on OneDrive-redirected
              Windows setups can resolve to a subfolder of the real user root
              (e.g. C:\\Users\\Boss\\OneDrive), incorrectly blocking Downloads.
  FIX-SAFE-2  The resolved Downloads and Desktop paths (via registry) are
              always added to allowed_roots, so they are never blocked even
              on exotic profile configurations.
"""

import os
import shutil
import time
import glob
import webbrowser
from pathlib import Path
from typing import Optional
from backend.plugins._base import Plugin
from backend.utils.logger import get_logger

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
        home = Path(os.environ.get("USERPROFILE") or os.path.expanduser("~"))
        for candidate in [home / "OneDrive" / "Desktop", home / "Desktop"]:
            if candidate.exists():
                return candidate
        return home / "Desktop"


def get_downloads_path() -> Path:
    """Robustly resolve the Windows Downloads path."""
    import winreg
    try:
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            reg_path, _ = winreg.QueryValueEx(key, "{374DE290-123F-4565-9164-39C4925E467B}")
            return Path(os.path.expandvars(reg_path))
    except Exception:
        home = Path(os.environ.get("USERPROFILE") or os.path.expanduser("~"))
        for candidate in [home / "Downloads", home / "OneDrive" / "Downloads"]:
            if candidate.exists():
                return candidate
        return home / "Downloads"


class FilePlugin(Plugin):
    name = "file_op"
    description = "Comprehensive file operations: read, write, list, copy, move, delete."
    parameters = {
        "operation": {
            "type": "string",
            "description": "The operation to perform: 'read', 'list', 'write', 'copy', 'move', 'delete', 'move_pattern', 'open', 'find', 'get_selection' (returns comma-separated paths).",
            "enum": ["read", "list", "write", "copy", "move", "delete", "move_pattern", "open", "find", "get_selection"],
            "required": True,
        },
        "path": {
            "type": "string",
            "description": "Target file or directory path. Use 'downloads', 'desktop', or 'documents' as shortcuts.",
            "required": False,
        },
        "source": {
            "type": "string",
            "description": "Source file path for copy/move",
            "required": False,
        },
        "content": {
            "type": "string",
            "description": "Content to write to file (use with operation='write')",
            "required": False,
        },
        "name": {
            "type": "string",
            "description": "Name or query for search (use with operation='find')",
            "required": False,
        },
        "search_path": {
            "type": "string",
            "description": "Base directory to search in (use with operation='find')",
            "required": False,
        },
        "mode": {
            "type": "string",
            "description": "Write mode: 'overwrite' or 'append'",
            "enum": ["overwrite", "append"],
            "required": False,
        },
        "pattern": {
            "type": "string",
            "description": "Glob pattern for move_pattern (e.g. '*.png')",
            "required": False,
        },
        "confirm": {
            "type": "boolean",
            "description": "Must be true to authorize deletion",
            "required": False,
        },
        "sort_by": {
            "type": "string",
            "description": "Sort directory listing by: 'date', 'name', 'size' (Default: date)",
            "enum": ["date", "name", "size"],
            "required": False,
        }
    }

    def _safe(self, path_str: str) -> Path:
        """
        Resolve path and verify it is under allowed roots.

        FIX-SAFE-1: Use USERPROFILE as the authoritative home root.
        os.path.expanduser("~") can return an OneDrive-redirected path on
        Windows (e.g. C:\\Users\\Boss\\OneDrive) which is a *subdirectory* of
        the real user root, causing sibling folders like Downloads to be
        incorrectly blocked.

        FIX-SAFE-2: Always include the registry-resolved Downloads and Desktop
        paths so they are never blocked regardless of profile configuration.
        """
        if not path_str:
            raise ValueError("Empty path provided")

        # FIX-SAFE-1: USERPROFILE is always the real user root on Windows.
        userprofile = os.environ.get("USERPROFILE")
        if userprofile:
            user_home = Path(userprofile).resolve()
        else:
            user_home = Path(os.path.expanduser("~")).resolve()

        p = Path(path_str).resolve()

        # Build allowed roots
        allowed_roots = {user_home}

        # OneDrive variants
        for env_var in ["OneDrive", "OneDriveConsumer", "OneDriveCommercial"]:
            val = os.environ.get(env_var)
            if val:
                allowed_roots.add(Path(val).resolve())

        # FIX-SAFE-2: Always allow the registry-resolved shell folders
        try:
            allowed_roots.add(get_downloads_path().resolve())
        except Exception:
            pass
        try:
            allowed_roots.add(get_desktop_path().resolve())
        except Exception:
            pass

        is_safe = any(p == root or root in p.parents for root in allowed_roots)

        if not is_safe:
            logger.warning(f"[SECURITY] Denied access outside allowed roots: {p}")
            raise PermissionError(f"Access denied: '{p}' is outside allowed directories.")

        return p

    def execute(self, operation: str = "", **params) -> str:
        try:
            # Handle Path Shortcuts
            path_str = params.get("path", "")
            if path_str.lower() == "downloads":
                params["path"] = str(get_downloads_path())
            elif path_str.lower() == "desktop":
                params["path"] = str(get_desktop_path())
            elif path_str.lower() == "documents":
                params["path"] = str(Path(os.environ.get("USERPROFILE") or os.path.expanduser("~")) / "Documents")

            if operation == "read":   return self._read_file(params)
            if operation == "write":  return self._write_file(params)
            if operation == "list":   return self._list_dir(params)
            if operation == "open":   return self._open_file(params)
            if operation == "find":   return self._find_file(params)
            if operation == "get_selection": return self._get_explorer_selection()

            source  = params.get("source")
            dest    = params.get("path") or params.get("dest")
            pattern = params.get("pattern")

            src = self._safe(source) if source else None
            dst = self._safe(dest)   if dest   else None

            if operation == "copy":
                shutil.copy2(str(src), str(dst))
                return f"Copied {src.name} to {dst}."
            if operation == "move":
                shutil.move(str(src), str(dst))
                return f"Moved {src.name} to {dst}."
            if operation == "delete":
                if not src: return "No path specified for delete."
                if src.is_dir(): return "I cannot delete directories for safety."
                if not params.get("confirm"):
                    return f"Sir, I require confirmation to delete {src.name}."
                src.unlink()
                return f"Successfully deleted {src.name}."
            if operation == "move_pattern" and pattern:
                count = 0
                for f in glob.glob(os.path.join(str(src), pattern)):
                    shutil.move(f, str(dst))
                    count += 1
                return f"Moved {count} files matching '{pattern}' to {dst}."

            return f"Unsupported file operation: {operation}"
        except Exception as e:
            logger.error(f"[FILE_OP] Error: {e}")
            return f"File operation failed: {str(e)}"

    def _open_file(self, params: dict) -> str:
        path = params.get("path")
        if not path: return "No path provided to open."
        safe_path = self._safe(path)
        os.startfile(safe_path)
        return f"Opening {safe_path.name}, Sir."

    def _find_file(self, params: dict) -> str:
        name = params.get("name") or params.get("query")
        if not name: return "What should I look for, Sir?"
        search_path = params.get("search_path")
        try:
            if search_path:
                bases = [self._safe(search_path)]
            else:
                home = Path(os.environ.get("USERPROFILE") or os.path.expanduser("~"))
                bases = [
                    get_desktop_path(),
                    get_downloads_path(),
                    home / "Documents",
                    home,
                ]
                for env in ["OneDrive", "OneDriveConsumer"]:
                    v = os.environ.get(env)
                    if v: bases.append(Path(v))
            results = []
            for base in set(bases):
                if not base.exists(): continue
                for match in base.rglob(f"*{name}*"):
                    results.append(str(match))
                    if len(results) >= 10: break
                if len(results) >= 10: break
            if not results: return f"Could not find any files matching '{name}'."
            return "Search results:\n" + "\n".join(results)
        except Exception as e:
            return f"Search failed: {e}"

    def _get_explorer_selection(self) -> str:
        """Capture selected file paths from the active Windows Explorer window."""
        try:
            import win32com.client
            shell = win32com.client.Dispatch("Shell.Application")
            windows = shell.Windows()
            
            # Find the focused (or at least an active) Explorer window
            selected_paths = []
            for window in windows:
                try:
                    # 'Explorer' or 'File Explorer' usually in FullName
                    if "explorer.exe" in window.FullName.lower():
                        items = window.Document.SelectedItems()
                        if items.Count > 0:
                            for i in range(items.Count):
                                selected_paths.append(items.Item(i).Path)
                            # We stop at the first window we find with a selection
                            break
                except:
                    continue
            
            if not selected_paths:
                return "I couldn't find any selected files in an active Explorer window, Sir. Please make sure the window is open and files are highlighted."
            
            # Return as a comma-separated list for easy handoff to other tools
            return ", ".join(selected_paths)
        except Exception as e:
            logger.error(f"[FILE_OP] Selection capture failed: {e}")
            return f"Failed to capture Explorer selection: {e}"

    def _write_file(self, params: dict) -> str:
        path_str = params.get("path", "")
        content  = params.get("content", "")
        mode     = params.get("mode", "overwrite")
        if not path_str:
            desktop = get_desktop_path() / "Yuki_Designs"
            desktop.mkdir(parents=True, exist_ok=True)
            path = desktop / f"design_{int(time.time())}.html"
        else:
            path = self._safe(path_str)
        path.parent.mkdir(parents=True, exist_ok=True)
        write_mode = "w" if mode == "overwrite" else "a"
        with open(path, write_mode, encoding="utf-8") as f:
            f.write(content)
        if path.suffix in [".html", ".htm"]:
            webbrowser.open(f"file:///{path}")
            return f"Design complete! Saved to {path.name} and opened in browser."
        return f"Successfully wrote to {path.name}."

    def _read_file(self, params: dict) -> str:
        path_str = params.get("path")
        if not path_str: return "No path specified to read."
        path = self._safe(path_str)
        if not path.exists(): return f"File not found: {path.name}"
        if path.is_dir():     return f"Cannot read {path.name} (it is a directory)."
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read(params.get("max_chars", 10000))
            suffix  = "... [TRUNCATED]" if f.read(1) else ""
            return content + suffix

    def _list_dir(self, params: dict) -> str:
        path_str = params.get("path") or "."
        path = self._safe(path_str)
        if not path.exists():  return f"Directory not found: {path}"
        if not path.is_dir():  return f"Path is not a directory: {path.name}"

        sort_by = params.get("sort_by", "date")
        items   = list(path.iterdir())

        if sort_by == "date":
            items.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        elif sort_by == "size":
            items.sort(key=lambda x: x.stat().st_size, reverse=True)
        else:
            items.sort(key=lambda x: x.name.lower())

        total      = len(items)
        items_slice = items[:50]

        lines = []
        for i in items_slice:
            st     = i.stat()
            prefix = "📁" if i.is_dir() else "📄"
            date   = time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime))
            size   = f"({st.st_size/1024:.1f} KB)" if not i.is_dir() else ""
            lines.append(f"{prefix} {i.name: <40} | {date} {size}")

        if not lines: return f"The directory {path.name} is empty."

        output  = f"Contents of {path.name} (Sorted by {sort_by}, showing 50 of {total}):\n"
        output += "-" * 70 + "\n"
        output += "\n".join(lines)
        return output