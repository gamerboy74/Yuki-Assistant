"""
terminal.py — Advanced PowerShell Terminal
Executes commands with safety checks and environment aware paths.
"""

import subprocess
from backend.plugins._base import Plugin
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Mandatory Security Blocklist
BLOCKED = ["rm -rf /", "mkfs", "rmdir /s /q c:\\windows", "del /f /s /q c:\\windows", ":(){ :|:& };:"]

class TerminalPlugin(Plugin):
    name = "run_command"
    description = """Execute a PowerShell command on the system.
Use for: git, npm, pip, directory listing, or running scripts.
Safety: Blocked for destructive system commands."""
    parameters = {
        "command": {"type": "string", "required": True, "description": "Command to run"}
    }

    def execute(self, command: str = "", **_) -> str:
        if not command: return "No command provided."
        
        # Security sanitization
        cmd_low = command.lower()
        if any(b in cmd_low for b in BLOCKED):
            return "Sir, that command is flagged as highly destructive. I cannot execute it for safety reasons."

        try:
            # Use PowerShell for Windows compatibility
            process = subprocess.run(
                ["powershell", "-Command", command],
                capture_output=True,
                text=True,
                timeout=30,
                encoding="utf-8",
                errors="replace"
            )
            
            output = process.stdout.strip()
            error = process.stderr.strip()
            
            if process.returncode == 0:
                if not output: return "Command executed successfully (no output)."
                return output[:2000] # Limit output size
            else:
                return f"Command failed with error:\n{error[:1000]}"
                
        except subprocess.TimeoutExpired:
            return "Operation timed out after 30 seconds."
        except Exception as e:
            logger.error(f"[TERMINAL] {e}")
            return f"Terminal failure: {str(e)[:150]}"
