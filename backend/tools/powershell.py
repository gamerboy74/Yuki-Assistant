"""
PowerShell sandbox — general-purpose Windows automation for Yuki.

The LLM generates a PowerShell script, we safety-check it,
execute it, and return stdout/stderr for the LLM to interpret.
"""

import subprocess
import os
from backend.utils.logger import get_logger
from backend.tools.safety import check_safety

logger = get_logger(__name__)


def run_powershell(script: str, timeout: int = 10) -> str:
    """
    Execute a PowerShell script in a sandboxed subprocess.
    
    Safety:
      - Checked against blocklist before execution
      - Timeout enforced (default 10s)
      - Working directory is user's home
      - Window is hidden
    
    Returns stdout + stderr combined, truncated to 2000 chars.
    """
    # Safety check
    is_safe, reason = check_safety(script)
    if not is_safe:
        return f"BLOCKED: {reason}"

    logger.info(f"[POWERSHELL] Executing: {script[:200]}")

    try:
        result = subprocess.run(
            ["powershell", "-WindowStyle", "Hidden", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.path.expanduser("~"),
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()

        # Combine output
        output = stdout
        if stderr and result.returncode != 0:
            output += f"\n[ERROR] {stderr}" if output else f"[ERROR] {stderr}"

        # Truncate to avoid blowing up the LLM context
        if len(output) > 2000:
            output = output[:2000] + "\n... (truncated)"

        if not output:
            output = f"Command completed (exit code {result.returncode})"

        logger.info(f"[POWERSHELL] Result: {output[:200]}")
        return output

    except subprocess.TimeoutExpired:
        logger.warning(f"[POWERSHELL] Timed out after {timeout}s")
        return f"Command timed out after {timeout} seconds."
    except Exception as e:
        logger.error(f"[POWERSHELL] Error: {e}")
        return f"PowerShell execution failed: {str(e)[:150]}"
