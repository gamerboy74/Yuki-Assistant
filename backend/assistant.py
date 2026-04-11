import sys
import os
import json
import asyncio
import threading
import time
from dotenv import load_dotenv

# Path setup
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=True)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.utils.logger import get_logger
from backend.config import cfg
from backend.utils.monitoring import get_system_stats
from backend.utils.weather import get_weather_data
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

def _log_event(text: str):
    """Log a system event to the HUD dashboard."""
    send({"type": "log", "text": text})
    logger.info(f"[HUD Log] {text}")

async def monitor_loop(stop_event: asyncio.Event):
    """Background monitoring loop."""
    while not stop_event.is_set():
        try:
            stats = get_system_stats()
            weather = await get_weather_data()
            if weather:
                stats["weather"] = weather
            send({"type": "status", "data": stats})
        except Exception:
            pass
        await asyncio.sleep(10)

async def main():
    """Entry point for the HP Yuki Voice Assistant."""
    logger.info("Initializing Yuki HP System...")
    _log_event("Initializing Yuki HP System...")
    
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
    
    async def _handle_get_voices_async():
        from backend.speech.synthesis import get_voices_async
        v_list = await get_voices_async()
        
        # Chunk into groups of 50 to prevent pipe flooding
        chunk_size = 50
        total_chunks = (len(v_list) + chunk_size - 1) // chunk_size
        
        for i in range(0, len(v_list), chunk_size):
            chunk = v_list[i : i + chunk_size]
            send({
                "type": "voices", 
                "data": chunk, 
                "chunk": (i // chunk_size) + 1,
                "total": total_chunks
            })
            # Small breath between bursts to keep event loop responsive
            await asyncio.sleep(0.1)
            
        logger.info(f"Dispatched {len(v_list)} neural identities to UI in {total_chunks} batches.")

    def _handle_get_voices():
        asyncio.create_task(_handle_get_voices_async())
    
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
                elif data.get("type") == "yuki:command": # Actually main.cjs sends raw command
                    cmd_data = data.get("value", {})
                    if cmd_data.get("type") == "get_voices":
                        loop.call_soon_threadsafe(_handle_get_voices)
                elif data.get("type") == "save_settings":
                    from backend.config import update_from_dict
                    new_val = data.get("value", {})
                    
                    # Check if provider specifically changed to announce it
                    old_provider = cfg.get("brain", {}).get("provider")
                    update_from_dict(new_val)
                    new_provider = cfg.get("brain", {}).get("provider")
                    
                    loop.call_soon_threadsafe(orchestrator.reload_config)
                    logger.info("Configuration reloaded from UI.")
                    
                    if old_provider != new_provider:
                        # Quick vocal confirmation of neural link swap
                        msg = f"Neural link established with {new_provider.title()}."
                        orchestrator.speak(msg)
                elif data.get("type") == "get_voices":
                    loop.call_soon_threadsafe(_handle_get_voices)
                elif data.get("type") == "preview_voice":
                    v_id = data.get("voiceId")
                    v_prov = data.get("provider", "edge-tts")
                    text = data.get("text", "Neural Link Established. This is a preview of my current vocal configuration.")
                    asyncio.run_coroutine_threadsafe(orchestrator.handle_preview_voice(text, v_id, v_prov), loop)
                elif data.get("type") == "purge_memory":
                    from backend import memory as mem
                    mem.clear_session_context()
                    logger.info("Memory vault purged.")
            except Exception as e:
                import traceback
                logger.error(f"Error in bridge stdin loop: {e}\n{traceback.format_exc()}")

    loop = asyncio.get_running_loop()
    threading.Thread(target=stdin_reader, daemon=True).start()
    
    # 4. Lifecycle Management
    mem.increment_session()
    greeting = mem.get_greeting() or cfg["assistant"]["greeting"]
    send({"type": "idle"})

    async def run_lifecycle():
        # A. Start neural priming in background
        _log_event("Priming neural pipelines...")
        orch_task = asyncio.create_task(orchestrator.start())
        
        # B. Parallel Wait for UI and Neural Priming
        # We want to greet as soon as BOTH are ready.
        try:
            # First, wait for the UI handshake (should be fast)
            await asyncio.wait_for(ui_ready_event.wait(), timeout=45)
            logger.info("UI handshake received.")
            _log_event("UI Connected. Establishing neural links...")
        except asyncio.TimeoutError:
            logger.warning("UI handshake timeout; proceeding anyway.")

        # C. Wait for neural priming to complete
        await orch_task
        
        # D. Greeting - Guaranteed UI and loaded voice
        msg = "Neural link established. Yuki is online."
        _log_event(msg)
        
        # Immediate UI state sync
        send({"type": "speaking"})
        send({"type": "response", "text": greeting})
        
        # Audible greeting
        await orchestrator.speak(greeting)
        send({"type": "idle"})
        
        # E. Post-Greeting: Launch background monitoring
        asyncio.create_task(monitor_loop(stop_event))

    # Run everything
    lifecycle_task = asyncio.create_task(run_lifecycle())
    
    msg = "Yuki status: Online. High-Performance neural links initialized."
    logger.info(msg)
    _log_event(msg)
    
    await stop_event.wait()
    orchestrator.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception:
        logger.exception("Fatal startup error in main loop")
