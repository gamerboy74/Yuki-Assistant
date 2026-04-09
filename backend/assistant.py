"""
Yuki Voice Assistant — Main Orchestrator
=========================================
Runs as a subprocess spawned by Electron.
Communicates via stdin/stdout JSON messages.

Message types sent TO Electron (stdout):
  {"type": "wake"}                         — wake word detected
  {"type": "listening"}                    — recording user command
  {"type": "transcript", "text": "..."}   — transcribed speech
  {"type": "processing"}                   — sending to brain
  {"type": "response", "text": "..."}     — Yuki's spoken response
  {"type": "clarify", "question": "...", "options": [...]}  — needs user choice
  {"type": "speaking"}                     — TTS playing
  {"type": "idle"}                         — back to standby

Message types received FROM Electron (stdin):
  {"type": "choice", "value": "..."}      — user selected a clarify option
  {"type": "manual_trigger"}              — user clicked the orb
  {"type": "stop"}                         — graceful shutdown
"""
import sys
import os
import json
import threading
import time
import queue
from dotenv import load_dotenv

# Load .env file (for OPENAI_API_KEY etc.)
# backend/assistant.py is one level below the project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=True)

# Add the project root to sys.path so "from backend.*" imports resolve
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.utils.logger import get_logger
from backend.config import cfg
from backend.speech.wake_word import WakeWordDetector
from backend.speech.recognition import recognize_speech
from backend.speech.synthesis import speak, speak_async
from backend.speech.ai_correction import correct_transcript
from backend.brain import process as brain_process
from backend.executor import execute
from backend import intent_router
from backend import memory as mem
from backend.proactive_agent import ProactiveAgent
from backend.utils.monitoring import get_system_stats

logger = get_logger(__name__)

# ── Globals ──────────────────────────────────────────────────────────────────
_choice_queue: queue.Queue       = queue.Queue()
_text_input_queue: queue.Queue   = queue.Queue()  # Typed messages from chat UI
_manual_trigger_event = threading.Event()
_interrupt_listen_event = threading.Event()
_stop_event = threading.Event()
_ui_ready_event = threading.Event()


# ── IPC helpers ───────────────────────────────────────────────────────────────
def send(msg: dict) -> None:
    """Send JSON message to Electron via stdout."""
    try:
        print(json.dumps(msg), flush=True)
    except Exception as e:
        logger.error(f"stdout send error: {e}")


def _stdin_reader():
    """
    Background thread: reads JSON lines from stdin (sent by Electron).
    Handles: choice, manual_trigger, stop
    """
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            msg_type = data.get("type", "")

            if msg_type == "ui_ready":
                _ui_ready_event.set()

            elif msg_type == "choice":
                _choice_queue.put(data.get("value", ""))
                _interrupt_listen_event.set()
                logger.info(f"Received choice: {data.get('value')}")

            elif msg_type == "manual_trigger":
                _manual_trigger_event.set()
                _interrupt_listen_event.set()
                logger.info("Manual trigger received from Electron")

            elif msg_type == "text_input":
                text = data.get("value", "").strip()
                if text.startswith("__settings__:"):
                    # We'll need the wake_detector instance, which is in the run() scope.
                    # For now, put it in a temporary storage if the thread hasn't started run()
                    # or handle it via a callback if we want to be clean.
                    # Easiest: save to a global or just let it update cfg.
                    payload_str = text[13:]
                    # If run() has started, we can pass the detector. 
                    # But wake_detector is a local. Let's make it a global or reachable.
                    _text_input_queue.put(text)
                elif text == "forget everything":
                    mem.clear_all()
                    logger.info("Purged all memory via GUI")
                elif text:
                    _text_input_queue.put(text)
                    _interrupt_listen_event.set()
                    logger.info(f"Text input received: {text!r}")

            elif msg_type == "stop":
                logger.info("Stop signal received")
                _stop_event.set()

        except json.JSONDecodeError:
            logger.debug(f"Invalid stdin JSON: {line!r}")


def _update_settings(payload_str: str, wake_detector: WakeWordDetector = None):
    """Parse GUI settings payload and update live parameters + save to yuki.config.json."""
    try:
        new_cfg = json.loads(payload_str)
        logger.info(f"Applying new settings: {new_cfg}")
        # Apply to live config
        cfg["assistant"]["tts_voice"] = new_cfg.get("tts_voice", cfg["assistant"].get("tts_voice"))
        cfg.setdefault("whisper", {})
        cfg["whisper"]["model_size"]        = new_cfg.get("whisper_model", "base")
        cfg["whisper"]["silence_threshold"] = new_cfg.get("silence_threshold", 300)
        cfg["whisper"]["silence_timeout"]   = new_cfg.get("silence_timeout", 1.2)
        cfg.setdefault("router", {})
        cfg["router"]["enabled"]            = new_cfg.get("router_enabled", True)
        
        # New: Wake word sensitivity
        sensitivity = new_cfg.get("wake_word_sensitivity", 0.7)
        cfg["assistant"]["wake_word_sensitivity"] = sensitivity
        if wake_detector:
            wake_detector.sensitivity = float(sensitivity)
            logger.info(f"Live sensitivity updated to {sensitivity}")

        # Update live environment variables if needed
        os.environ["OLLAMA_BASE_URL"] = new_cfg.get("ollama_url", "http://localhost:11434")

        # Save to disk
        from backend.config import CONFIG_FILE
        # Since we modified the dict in place, we can dump it
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4)
        logger.info("Settings saved to yuki.config.json")
    except Exception as e:
        logger.error(f"Failed to update settings: {e}")

def _wait_for_choice(timeout: float = 30.0) -> str:
    """Block until user picks a clarify option (via Electron UI) or timeout."""
    try:
        return _choice_queue.get(timeout=timeout)
    except queue.Empty:
        return ""


# ── Main loop ─────────────────────────────────────────────────────────────────
def _handle_memory_intent(transcript: str) -> str | None:
    """
    Fast-path memory handler. Intercepts phrases like:
      - "remember X"
      - "call me X"
      - "my name is X"
      - "always call me X"
    Saves to memory and returns a short spoken confirmation.
    Returns None if no memory intent matched.
    """
    t = transcript.lower().strip()

    # ── "call me X" / "always call me X" ────────────────────────────────
    for prefix in ["always call me ", "call me ", "from now call me "]:
        if prefix in t:
            name = transcript[t.index(prefix) + len(prefix):].strip().split()[0].strip(".,!")
            if name:
                mem.set_preference("greeting_title", name)
                mem.remember(f"call me {name}")
                return f"Got it, {name}."

    # ── "my name is X" ───────────────────────────────────────────────────
    for prefix in ["my name is ", "i am ", "you can call me "]:
        if t.startswith(prefix):
            name = transcript[len(prefix):].strip().split()[0].strip(".,!")
            if name:
                mem.set_user("name", name)
                return f"Nice to meet you, {name}."

    # ── "remember X" ─────────────────────────────────────────────────────
    for prefix in ["remember that ", "remember ", "please remember ", "don't forget "]:
        if t.startswith(prefix):
            fact = transcript[len(prefix):].strip()
            if fact:
                mem.remember(fact)
                return "Got it."

    return None  # No memory pattern matched — let the LLM handle it


# Removed _prewarm_whisper to prevent GIL blocking on startup.
# Model will be lazy-loaded on the very first voice command instead.


def run():
    """Main voice agent loop."""
    _name     = cfg["assistant"]["name"]
    wake_detector = WakeWordDetector(wake_words=cfg["assistant"]["wake_words"])

    # Track this session in memory
    mem.increment_session()

    # Personalised greeting using stored preferences / user name
    _greeting = mem.get_greeting() or cfg["assistant"]["greeting"]

    logger.info("Step 1: Initializing threads...")
    # Start stdin reader thread
    stdin_thread = threading.Thread(target=_stdin_reader, daemon=True)
    stdin_thread.start()

    # Start system monitoring thread
    monitor_thread = threading.Thread(target=_monitor_loop, daemon=True)
    monitor_thread.start()

    logger.info("Step 2: Skipped pre-warming to maintain UI responsiveness...")
    
    logger.info("Step 3: App warmup delay...")
    logger.info(f"Step 3: Greeting user with: {_greeting}")
    # Run the greeting in a background thread so the main loop starts instantly
    # and the UI doesn't freeze while waiting for TTS generation or playback
    _silent_wake_event = threading.Event()

    def _startup_greeting():
        # Unlock the UI instantly by setting it to idle
        send({"type": "idle"})
        
        # Wait until React completes its fade-in animation and sends the explicit "ui_ready" IPC event.
        # This guarantees deterministic timing regardless of CPU load.
        _ui_ready_event.wait(timeout=10.0)

        send({"type": "speaking"})
        send({"type": "response", "text": _greeting})
        speak(_greeting)
        
        # Automatically transition into listening mode after the morning briefing
        if not _manual_trigger_event.is_set() and not _stop_event.is_set():
            _silent_wake_event.set()

    threading.Thread(target=_startup_greeting, daemon=True).start()

    logger.info("Step 5: Initialization complete. Entering main loop...")

    _proactive = ProactiveAgent(speak_fn=speak, send_fn=send)
    _proactive.start()

    # After completing a task, stay hot for this many seconds (no wake word needed)
    HOT_WINDOW_SECS = 6
    _hot_transcript: str | None = None  # Pre-loaded follow-up from hot window

    # Random witty wake acknowledgements (replaces the bland 'Yes?')
    import random
    _WAKE_ACKS = [
        "Yes?",
        "Hmm?",
        "Go ahead.",
        "What's up?",
        "I'm listening.",
        "Yeah, boss?",
        "Ready.",
        "On it — what do you need?",
    ]

    while not _stop_event.is_set():
        try:
            # ── 1. Wait for wake word or manual trigger ──────────────────────
            send({"type": "idle"})

            triggered = False
            text_from_ui = None
            is_silent_wake = False

            # ── Hot window shortcut: skip wake detection if follow-up already queued ──
            if _hot_transcript:
                triggered = True
                transcript = _hot_transcript
                _hot_transcript = None
                send({"type": "wake"})
                send({"type": "transcript", "text": transcript})
                send({"type": "processing"})
                result = intent_router.route(transcript)
                if result is None:
                    result = brain_process(transcript)
            else:
                # Check for typed message first (instant — no audio needed)
                try:
                    text_from_ui = _text_input_queue.get_nowait()
                    triggered = True
                    logger.info(f"Processing text input directly: {text_from_ui!r}")
                except queue.Empty:
                    pass
                result = None  # will be set below after wake/transcribe

            if not triggered:
                # Start wake word detection in a background thread so we can also
                # respond to the manual trigger
                wake_result = threading.Event()
                def _wake_thread():
                    if wake_detector.listen_for_wake_word():
                        wake_result.set()

                wt = threading.Thread(target=_wake_thread, daemon=True)
                wt.start()

                # Poll: wake event OR manual click
                while not _stop_event.is_set():
                    if _manual_trigger_event.is_set():
                        # Cancel the background audio thread before proceeding
                        wake_detector.stop()
                        _manual_trigger_event.clear()
                        triggered = True
                        break
                    if wake_result.is_set():
                        wake_result.clear()
                        triggered = True
                        break

                    if _silent_wake_event.is_set():
                        _silent_wake_event.clear()
                        wake_detector.stop() # Cancel background listening
                        triggered = True
                        is_silent_wake = True
                        break

                    # Also check for typed messages while waiting for wake word
                    try:
                        text_from_ui = _text_input_queue.get_nowait()
                        if text_from_ui.startswith("__settings__:"):
                            _update_settings(text_from_ui[13:], wake_detector)
                            text_from_ui = None
                            continue # Keep waiting for wake after settings update
                        
                        wake_detector.stop()
                        triggered = True
                        break
                    except queue.Empty:
                        pass
                    time.sleep(0.1)

            if result is None:
                if not triggered or _stop_event.is_set():
                    # Also cancel any still-running wake thread on global stop
                    wake_detector.stop()
                    continue

                # ── 2. Signal wake ───────────────────────────────────────────────
                send({"type": "wake"})

                # ── 3. Record + transcribe ───────────────────────────────────────
                if text_from_ui:
                    transcript = text_from_ui

                else:
                    if not is_silent_wake:
                        speak(random.choice(_WAKE_ACKS))
                    send({"type": "listening"})
                    _interrupt_listen_event.clear()
                    transcript = recognize_speech(timeout=6.0, interrupt_event=_interrupt_listen_event)

                    if not transcript:
                        # If recognition was interrupted by a manual click, just go idle silently
                        if _manual_trigger_event.is_set():
                            _manual_trigger_event.clear()
                            send({"type": "idle"})
                            continue

                        # Otherwise check if there's a typed message waiting
                        try:
                            transcript = _text_input_queue.get_nowait()
                        except queue.Empty:
                            pass

                    if not transcript:
                        send({"type": "idle"})
                        speak("I didn't catch that.")
                        continue

                    transcript = correct_transcript(transcript)
                    send({"type": "transcript", "text": transcript})

                # ── 4. Fast-path intent router (no LLM needed) ───────────────────
                send({"type": "processing"})
                result = intent_router.route(transcript)

                # ── 5. Fallback: AI brain if router didn't match ──────────────────
                if result is None:
                    result = brain_process(transcript)

            # ── 6. Clarification / Follow-up flow ─────────────────────────────
            while result.get("needs_clarify"):
                question = result.get("question", "Could you clarify?")
                options  = result.get("options", [])

                send({
                    "type": "clarify",
                    "question": question,
                    "options": options,
                })
                # Just speak the question naturally, don't read the robotic options array
                speak(question)

                send({"type": "listening"})
                _interrupt_listen_event.clear()
                clarify_transcript = recognize_speech(timeout=8.0, interrupt_event=_interrupt_listen_event)
                
                user_reply = None
                try:
                    user_reply = _choice_queue.get_nowait()
                except queue.Empty:
                    user_reply = clarify_transcript

                # If still no reply, check the typed text queue
                if not user_reply:
                    try:
                        tr = _text_input_queue.get_nowait()
                        if tr.startswith("__settings__"):
                            _update_settings(tr[13:], wake_detector)
                        else:
                            user_reply = tr
                            _interrupt_listen_event.set()
                    except queue.Empty:
                        pass

                if not user_reply:
                    if _manual_trigger_event.is_set():
                        _manual_trigger_event.clear()
                        send({"type": "idle"})
                        break
                    speak("I didn't catch that. Let me know when you're ready.")
                    break

                # Clear result response so it doesn't speak again in Step 9
                if result.get("response") == question:
                    result["response"] = None

                logger.info(f"User follow-up: {user_reply!r}")
                send({"type": "transcript", "text": user_reply})
                send({"type": "processing"})
                # Route through router again on clarification? Usually LLM brain knows the context.
                result = brain_process(user_reply)

            # ── 7. Memory fast-path (intercept before executor) ───────────────
            override_response = _handle_memory_intent(transcript) or None

            # ── 8. Execute action (fast-router results only) ──────────────────
            # Brain results (from the agentic loop) already executed tools
            # internally — they arrive here as a final response string.
            # Only fast-router results have an "action" that needs executing.
            if override_response is None:
                action = result.get("action") or {"type": "none", "params": {}}
                if action.get("type") not in ("none", None):
                    res = execute(action)
                    if res:
                        override_response = res

            # ── 9. Speak response ─────────────────────────────────────────────
            if isinstance(override_response, dict):
                speak_text = override_response.get("speak", "")
                ui_text = override_response.get("ui_log", "") or speak_text
                if speak_text or ui_text:
                    send({"type": "speaking"})
                    send({"type": "response", "text": ui_text})
                    if speak_text:
                        speak(speak_text)
            else:
                response_text = override_response or result.get("response") or ""
                if response_text:
                    send({"type": "speaking"})
                    send({"type": "response", "text": response_text})
                    speak(response_text)

            send({"type": "idle"})

            # ── 10. Hot-listen window ─────────────────────────────────────────
            # Stay alert for HOT_WINDOW_SECS after every task.
            # If user speaks again, skip next wake-word cycle entirely.
            send({"type": "listening"})
            _interrupt_listen_event.clear()
            hot_follow_up = recognize_speech(timeout=HOT_WINDOW_SECS, interrupt_event=_interrupt_listen_event)
            send({"type": "idle"})
            
            # If user clicked to cancel during hot window, just stop
            if _manual_trigger_event.is_set():
                _manual_trigger_event.clear()
                _hot_transcript = None
            elif hot_follow_up:
                logger.info(f"[HOT] Follow-up: {hot_follow_up!r}")
                _hot_transcript = correct_transcript(hot_follow_up)
            else:
                logger.info("[HOT] Silent — going to sleep.")
                _hot_transcript = None

        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt — shutting down")
            _proactive.stop()
            break
        except Exception as e:
            logger.error(f"Main loop error: {e}")
            send({"type": "idle"})
            time.sleep(1)

    _proactive.stop()

def _monitor_loop():
    """Background thread to periodically send system stats to Electron."""
    while not _stop_event.is_set():
        try:
            stats = get_system_stats()
            send({"type": "status", "data": stats})
        except Exception as e:
            logger.error(f"Monitoring error: {e}")
        time.sleep(10) # Update every 10 seconds


if __name__ == "__main__":
    run()
