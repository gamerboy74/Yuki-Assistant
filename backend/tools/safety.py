"""
Safety layer for PowerShell execution.

Blocks dangerous commands before they reach the shell.
All blocked attempts are logged for audit.
"""

import re
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# ── Blocked patterns ──────────────────────────────────────────────────────────
# These will NEVER be executed, regardless of what the LLM generates.

_BLOCKED_PATTERNS = [
    # Destructive system commands
    r"Format-Volume",
    r"Clear-Disk",
    r"Stop-Computer",
    r"Restart-Computer",
    r"shutdown\s",
    r"Disable-NetAdapter",

    # Dangerous file ops (recursive delete on system dirs)
    r"Remove-Item\s+.*-Recurse.*[A-Z]:\\(?:Windows|Program)",
    r"rm\s+-rf\s+/",
    r"del\s+/[sS]\s+[A-Z]:\\",
    r"rmdir\s+/[sS]\s+[A-Z]:\\",

    # Execution policy / security bypass
    r"Set-ExecutionPolicy\s+Unrestricted",
    r"Set-ExecutionPolicy\s+Bypass",
    r"Bypass\s+-Scope\s+Process",

    # Download + execute (malware pattern)
    r"Invoke-WebRequest.*\|\s*Invoke-Expression",
    r"IEX\s*\(",
    r"Invoke-Expression.*Invoke-WebRequest",
    r"iwr.*\.exe.*-OutFile",
    r"curl.*\.exe.*-o\s",
    r"wget.*\.exe.*-O\s",

    # Registry damage
    r"Remove-Item.*HKLM:",
    r"Remove-ItemProperty.*HKLM:",
    r"reg\s+delete\s+HKLM",

    # Network attacks
    r"Test-NetConnection.*-Port.*1\.\.65535",
    r"nmap\s",
    r"Invoke-Mimikatz",

    # Credential theft
    r"Get-Credential",
    r"ConvertTo-SecureString",
    r"Export-Clixml.*credential",

    # Disable security
    r"Set-MpPreference\s+-DisableRealtimeMonitoring",
    r"Disable-WindowsOptionalFeature.*Defender",
    r"netsh\s+firewall\s+set.*disable",
    r"netsh\s+advfirewall\s+set.*state\s+off",
]

_COMPILED_BLOCKS = [re.compile(p, re.IGNORECASE) for p in _BLOCKED_PATTERNS]


def check_safety(script: str) -> tuple[bool, str]:
    """
    Check a PowerShell script for dangerous patterns.
    
    Returns:
        (is_safe, reason) — True if safe, False with reason if blocked.
    """
    for pattern in _COMPILED_BLOCKS:
        if pattern.search(script):
            reason = f"Blocked dangerous command: {pattern.pattern}"
            logger.warning(f"[SAFETY] {reason} in script: {script[:200]}")
            return False, reason

    return True, ""


def sanitize_path(path: str) -> bool:
    """Check if a path is within the user's home directory."""
    import os
    from pathlib import Path

    home = Path(os.path.expanduser("~")).resolve()
    try:
        target = Path(path).resolve()
        return home in target.parents or target == home
    except Exception:
        return False
