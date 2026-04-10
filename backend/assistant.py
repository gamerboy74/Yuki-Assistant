import sys
import os
import json
import asyncio
import threading
from dotenv import load_dotenv

# Path setup
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=True)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.utils.logger import get_logger
from backend.config import cfg
from backend.utils.monitoring import get_system_stats
from backend.core.orchestrator import YukiOrchestrator
from backend.speech.synthesis import speak
from backend import memory as mem

logger = get_logger(__name__)

# IPC helpers
def send(msg: dict) -> None:
    try:
        print(json.dumps(msg), flush=True)
    except Exception as e:
        logger.error(f"stdout send error: {e}")

async def monitor_loop(stop_event: asyncio.Event):
    """Background monitoring loop."""
    while not stop_event.is_set():
        try:
            stats = get_system_stats()
            send({"type": "status", "data": stats})
        except Exception:
            pass
        await asyncio.sleep(10)

async def main():
    """Entry point for the HP Yuki Voice Assistant."""
    logger.info("Initializing Yuki HP System...")
    
    # 1. State
    stop_event = asyncio.Event()
    ui_ready_event = asyncio.Event()
    
    # 2. Orchestrator
    orchestrator = YukiOrchestrator(send_fn=send)

    def _activate_manual_trigger():
        """Force assistant into active listening mode from UI trigger."""
        asyncio.create_task(orchestrator.handle_manual_trigger())

    def _handle_text_input(text: str):
        """Route typed chat input into orchestrator text turn flow."""
        asyncio.create_task(orchestrator.handle_text_input(text))

    def _cancel_manual_trigger():
        """Cancel active listening mode from UI trigger toggle."""
        asyncio.create_task(orchestrator.handle_cancel_listening())
    
    # 3. Simple stdin handler (legacy bridge)
    def stdin_reader():
        for line in sys.stdin:
            try:
                data = json.loads(line)
                if data.get("type") == "stop":
                    loop.call_soon_threadsafe(stop_event.set)
                elif data.get("type") == "ui_ready":
                    loop.call_soon_threadsafe(ui_ready_event.set)
                elif data.get("type") == "manual_trigger":
                    loop.call_soon_threadsafe(_activate_manual_trigger)
                elif data.get("type") == "cancel_listening":
                    loop.call_soon_threadsafe(_cancel_manual_trigger)
                elif data.get("type") in ("text_input", "message"):
                    loop.call_soon_threadsafe(_handle_text_input, str(data.get("value", "")))
                elif data.get("type") == "choice":
                    loop.call_soon_threadsafe(_handle_text_input, str(data.get("value", "")))
            except: pass

    loop = asyncio.get_running_loop()
    threading.Thread(target=stdin_reader, daemon=True).start()
    
    # 4. Greeting
    mem.increment_session()
    greeting = mem.get_greeting() or cfg["assistant"]["greeting"]
    send({"type": "idle"})

    async def emit_startup_greeting():
        try:
            # Wait for renderer handshake so greeting is not lost during boot.
            await asyncio.wait_for(ui_ready_event.wait(), timeout=8)
        except asyncio.TimeoutError:
            logger.warning("UI ready signal timed out; sending greeting anyway")
        send({"type": "speaking"})
        send({"type": "response", "text": greeting})
        # Speak greeting to completion, then restore explicit idle state.
        await asyncio.to_thread(speak, greeting)
        send({"type": "idle"})
    
    # Launch Orchestrator and Monitor
    async with asyncio.TaskGroup() as tg:
        tg.create_task(monitor_loop(stop_event))
        tg.create_task(orchestrator.start())
        tg.create_task(emit_startup_greeting())
        
        # We can speak the greeting using the orchestrator's voice switcher
        # but let's just let the loop run
        logger.info("Yuki is online and listening (HP-VAD Mode).")
        await stop_event.wait()
        orchestrator.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Fatal startup error: {e}")
