"""
utils/safety.py — Safety layer for system and shell execution.
Blocks dangerous patterns before they reach the OS.
"""

import re
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_BLOCKED_PATTERNS = [
    r"Format-Volume",
    r"Clear-Disk",
    r"Stop-Computer",
    r"Restart-Computer",
    r"shutdown\s",
    r"Disable-NetAdapter",
    r"Remove-Item\s+.*-Recurse.*[A-Z]:\\(?:Windows|Program)",
    r"rm\s+-rf\s+/",
    r"del\s+/[sS]\s+[A-Z]:\\",
    r"rmdir\s+/[sS]\s+[A-Z]:\\",
    r"Set-ExecutionPolicy\s+Unrestricted",
    r"Set-ExecutionPolicy\s+Bypass",
    r"Invoke-WebRequest.*\|\s*Invoke-Expression",
    r"IEX\s*\(",
    r"reg\s+delete\s+HKLM",
    r"nmap\s",
    r"Invoke-Mimikatz",
    r"Set-MpPreference\s+-DisableRealtimeMonitoring",
]

_COMPILED_BLOCKS = [re.compile(p, re.IGNORECASE) for p in _BLOCKED_PATTERNS]

def is_safe_command(cmd: str) -> tuple[bool, str]:
    """Check a command string for dangerous patterns."""
    for pattern in _COMPILED_BLOCKS:
        if pattern.search(cmd):
            reason = f"Blocked dangerous command: {pattern.pattern}"
            logger.warning(f"[SAFETY] {reason}")
            return False, reason
    return True, ""
