"""
Yuki Brain CLI Tester
=====================
Directly tests the brain + executor pipeline without mic or TTS.
Run from the project root:

    python -m tests.test_brain_cli

Or with a one-liner command:
    python -m tests.test_brain_cli "open whatsapp"
"""
import sys
import os
import json

# ── setup path & env ──────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from backend.brain import process as brain_process, get_active_provider
from backend.executor import execute

# ── colour helpers ────────────────────────────────────────────────────────────
def _c(text, code): return f"\033[{code}m{text}\033[0m"
cyan   = lambda t: _c(t, "36")
green  = lambda t: _c(t, "32")
yellow = lambda t: _c(t, "33")
red    = lambda t: _c(t, "31")
bold   = lambda t: _c(t, "1")

# ── test commands ─────────────────────────────────────────────────────────────
DEFAULT_COMMANDS = [
    "open whatsapp",
    "what time is it",
    "search the web for weather in delhi",
    "open notepad",
    "play Aadat song on youtube",
    "take a screenshot",
    "what is your name",
]

def run_test(command: str):
    """Send one command through brain → executor and print results."""
    print("\n" + "─" * 60)
    print(bold(f"▶ Command : ") + cyan(command))

    result = brain_process(command)

    needs_clarify = result.get("needs_clarify", False)
    action        = result.get("action") or {"type": "none", "params": {}}
    response      = result.get("response", "")
    question      = result.get("question", "")
    options       = result.get("options", [])

    print(bold("  Action  : ") + yellow(json.dumps(action)))

    if needs_clarify:
        print(bold("  Clarify : ") + yellow(question))
        print(bold("  Options : ") + ", ".join(options))
    else:
        override = execute(action)
        final_response = override or response
        print(bold("  Response: ") + green(final_response or "(no response)"))
        if override:
            print(bold("  Executor: ") + green(f"override → {override}"))

    print(bold("  Raw JSON: ") + json.dumps(result, ensure_ascii=False, indent=2)[:400])


def main():
    print(bold("\n🌸 Yuki Brain CLI Tester"))
    print(f"   Provider : {cyan(get_active_provider())}")
    print(f"   Ollama   : http://localhost:11434")

    commands = sys.argv[1:] if len(sys.argv) > 1 else DEFAULT_COMMANDS

    for cmd in commands:
        try:
            run_test(cmd)
        except Exception as e:
            print(red(f"  ERROR: {e}"))

    print("\n" + "─" * 60)
    print(green("✅ All tests complete.\n"))


if __name__ == "__main__":
    main()
