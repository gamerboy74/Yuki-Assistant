"""
File search tool — safely find files in the user's home directory.
"""

import os
from pathlib import Path
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_DEFAULT_DIRS = [
    "Downloads",
    "Desktop",
    "Documents",
    os.path.join("OneDrive", "Downloads"),
    os.path.join("OneDrive", "Documents"),
    os.path.join("OneDrive", "Desktop"),
]


def find_file(name: str, search_dirs: list[str] | None = None) -> str:
    """
    Search for files matching *name* (case-insensitive substring match)
    in common user directories.
    
    Returns a list of matching file paths, or a 'not found' message.
    Sandboxed to %USERPROFILE%.
    """
    home = Path(os.path.expanduser("~"))
    name_lower = name.lower().strip()

    if not name_lower:
        return "No filename provided."

    dirs_to_search = []
    if search_dirs:
        for d in search_dirs:
            p = Path(d) if os.path.isabs(d) else home / d
            if p.exists() and p.is_dir():
                # Verify it's under home
                try:
                    p.resolve().relative_to(home.resolve())
                    dirs_to_search.append(p)
                except ValueError:
                    continue
    else:
        for d in _DEFAULT_DIRS:
            p = home / d
            if p.exists():
                dirs_to_search.append(p)

    if not dirs_to_search:
        return "No valid search directories found."

    matches = []
    for folder in dirs_to_search:
        try:
            for f in folder.iterdir():
                if f.is_file() and name_lower in f.name.lower():
                    matches.append(str(f))
                    if len(matches) >= 10:  # cap results
                        break
        except PermissionError:
            continue

    if matches:
        result = f"Found {len(matches)} file(s):\n"
        for m in matches:
            size_kb = os.path.getsize(m) / 1024
            result += f"  • {m} ({size_kb:.0f} KB)\n"
        logger.info(f"[FILE] Found {len(matches)} matches for '{name}'")
        return result.strip()
    
    searched = ", ".join(str(d) for d in dirs_to_search)
    return f"No files matching '{name}' found in: {searched}"
