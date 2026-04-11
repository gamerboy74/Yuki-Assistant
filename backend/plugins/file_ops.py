"""
File Operations Plugin — read, write, and manage files safely.
Restricts access to the user's home directory for safety.
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
        home = Path(os.path.expanduser("~"))
        for candidate in [home / "OneDrive" / "Desktop", home / "Desktop"]:
            if candidate.exists():
                return candidate
        return home / "Desktop"

class FilePlugin(Plugin):
    name = "file_op"
    description = "File ops: write, copy, move, delete."
    parameters = {
        "operation": {
            "type": "string",
            "description": "The operation to perform: 'write', 'copy', 'move', 'delete', 'move_pattern'",
            "enum": ["write", "copy", "move", "delete", "move_pattern"],
            "required": True,
        },
        "path": {
            "type": "string",
            "description": "Target file path or destination for copy/move",
            "required": False,
        },
        "source": {
            "type": "string",
            "description": "Source file path for copy/move",
            "required": False,
        },
        "content": {
            "type": "string",
            "description": "Content to write to file",
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
        }
    }

    def _safe(self, path_str: str) -> Path:
        """Resolve path and verify it is under %USERPROFILE%."""
        user_home = Path(os.path.expanduser("~")).resolve()
        if not path_str:
            raise ValueError("Empty path provided")
        p = Path(path_str).resolve()
        # Allow paths under user home or OneDrive
        if user_home not in p.parents and p != user_home:
            # Check for OneDrive variant
            if "OneDrive" not in str(p):
                 raise PermissionError(f"Access denied: '{p}' is outside your home directory.")
        return p

    def execute(self, operation: str = "", **params) -> str:
        try:
            if operation == "write":
                return self._write_file(params)
            
            source = params.get("source")
            dest = params.get("path") or params.get("dest") # handle both param names
            pattern = params.get("pattern")
            
            src = self._safe(source) if source else None
            dst = self._safe(dest) if dest else None

            if operation == "copy":
                shutil.copy2(str(src), str(dst))
                return f"Copied {src.name} to {dst}."
            elif operation == "move":
                shutil.move(str(src), str(dst))
                return f"Moved {src.name} to {dst}."
            elif operation == "delete":
                if not src: return "No path specified for delete."
                if src.is_dir(): return "I cannot delete directories for safety. Please do it manually."
                src.unlink()
                return f"Deleted file {src.name}."
            elif operation == "move_pattern" and pattern:
                count = 0
                for f in glob.glob(os.path.join(str(src), pattern)):
                    shutil.move(f, str(dst))
                    count += 1
                return f"Moved {count} files matching '{pattern}' to {dst}."
            
            return f"Unsupported file operation: {operation}"

        except Exception as e:
            logger.error(f"[FILE_OP] Error: {e}")
            return f"File operation failed: {str(e)}"

    def _write_file(self, params: dict) -> str:
        path_str = params.get("path", "")
        content = params.get("content", "")
        mode = params.get("mode", "overwrite")
        
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

class DesignWebPagePlugin(FilePlugin):
    name = "design_web_page"
    description = "Save and open web page design."
    parameters = {
        "content": {
            "type": "string",
            "description": "The full HTML/CSS code for the page",
            "required": True,
        },
        "path": {
            "type": "string",
            "description": "Optional filename/path",
            "required": False,
        }
    }
    
    def execute(self, content: str = "", **params) -> str:
        params["content"] = content
        params["operation"] = "write"
        return super()._write_file(params)
