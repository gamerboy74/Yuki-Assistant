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
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

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

logger = get_logger(__name__)

# ── Globals ──────────────────────────────────────────────────────────────────
_choice_queue: queue.Queue       = queue.Queue()
_text_input_queue: queue.Queue   = queue.Queue()  # Typed messages from chat UI
_manual_trigger_event = threading.Event()
_stop_event = threading.Event()


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

            if msg_type == "choice":
                _choice_queue.put(data.get("value", ""))
                logger.info(f"Received choice: {data.get('value')}")

            elif msg_type == "manual_trigger":
                _manual_trigger_event.set()
                logger.info("Manual trigger received from Electron")

            elif msg_type == "text_input":
                text = data.get("value", "").strip()
                if text.startswith("__settings__:"):
                    payload_str = text[13:] # strip prefix
                    _update_settings(payload_str)
                elif text == "forget everything":
                    mem.clear_all()
                    logger.info("Purged all memory via GUI")
                    # Optionally speak confirmation if it wasn't triggered silently
                elif text:
                    _text_input_queue.put(text)
                    logger.info(f"Text input received: {text!r}")

            elif msg_type == "stop":
                logger.info("Stop signal received")
                _stop_event.set()

        except json.JSONDecodeError:
            logger.debug(f"Invalid stdin JSON: {line!r}")


def _update_settings(payload_str: str):
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


def _prewarm_whisper():
    """Load the Whisper model before the main loop so first recognition is fast."""
    try:
        from backend.speech.recognition import _get_whisper
        send({"type": "loading", "text": "Loading speech model..."})
        _get_whisper()
        logger.info("Whisper model pre-warmed.")
    except Exception as e:
        logger.warning(f"Whisper pre-warm failed: {e}")


def run():
    """Main voice agent loop."""
    _name     = cfg["assistant"]["name"]
    wake_detector = WakeWordDetector(wake_words=cfg["assistant"]["wake_words"])

    # Track this session in memory
    mem.increment_session()

    # Personalised greeting using stored preferences / user name
    _greeting = mem.get_greeting() or cfg["assistant"]["greeting"]

    # Start stdin reader thread
    stdin_thread = threading.Thread(target=_stdin_reader, daemon=True)
    stdin_thread.start()

    # Pre-warm the Whisper model so first recognition is fast
    _prewarm_whisper()

    send({"type": "idle"})
    speak(_greeting)

    logger.info("Yuki is running. Waiting for wake word...")

    while not _stop_event.is_set():
        try:
            # ── 1. Wait for wake word or manual trigger ──────────────────────
            send({"type": "idle"})
            _manual_trigger_event.clear()

            triggered = False
            text_from_ui = None

            # Check for typed message first (instant — no audio needed)
            try:
                text_from_ui = _text_input_queue.get_nowait()
                triggered = True
                logger.info(f"Processing text input directly: {text_from_ui!r}")
            except queue.Empty:
                pass

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
                        triggered = True
                        break
                    if wake_result.is_set():
                        triggered = True
                        break
                    # Also check for typed messages while waiting for wake word
                    try:
                        text_from_ui = _text_input_queue.get_nowait()
                        wake_detector.stop()
                        triggered = True
                        break
                    except queue.Empty:
                        pass
                    time.sleep(0.1)

            if not triggered or _stop_event.is_set():
                # Also cancel any still-running wake thread on global stop
                wake_detector.stop()
                continue

            # ── 2. Signal wake ───────────────────────────────────────────────
            send({"type": "wake"})

            # ── 3. Record + transcribe ───────────────────────────────────────
            if text_from_ui:
                # Typed input — skip TTS "Yes?" and audio recording, UI already appended it
                transcript = text_from_ui
                # send({"type": "transcript", "text": transcript}) # Removed to prevent double bubble

            else:
                speak("Yes?")
                send({"type": "listening"})
                transcript = recognize_speech(timeout=6.0)

                if not transcript:
                    send({"type": "idle"})
                    speak("I didn't catch that. Try again.")
                    continue

                # Run local Gemma STT correction only when mishear patterns are present
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
                clarify_transcript = recognize_speech(timeout=8.0)
                
                # Check if user clicked a UI option quickly while it was listening
                try:
                    ui_choice = _choice_queue.get_nowait()
                except queue.Empty:
                    ui_choice = None

                user_reply = ui_choice if ui_choice else clarify_transcript

                if not user_reply:
                    speak("I didn't catch that. Let me know when you're ready.")
                    break

                logger.info(f"User follow-up: {user_reply!r}")
                send({"type": "transcript", "text": user_reply})
                send({"type": "processing"})
                # Route through router again on clarification? Usually LLM brain knows the context.
                result = brain_process(user_reply)

            # ── 7. Memory fast-path (intercept before executor) ───────────────
            override_response = _handle_memory_intent(transcript) or None

            # ── 8. Execute OS action (skip if memory already handled it) ──────
            if override_response is None:
                action = result.get("action") or {"type": "none", "params": {}}
                override_response = execute(action)

            # ── 8. Speak response ─────────────────────────────────────────────
            if isinstance(override_response, dict):
                speak_text = override_response.get("speak", "")
                ui_text = override_response.get("ui_log", "") or speak_text
                if speak_text or ui_text:
                    send({"type": "speaking"})
                    send({"type": "response", "text": ui_text})
                    if speak_text:
                        speak_async(speak_text)
            else:
                response_text = override_response or result.get("response") or ""
                if response_text:
                    send({"type": "speaking"})
                    send({"type": "response", "text": response_text})
                    speak_async(response_text)

            send({"type": "idle"})

        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt — shutting down")
            break
        except Exception as e:
            logger.error(f"Main loop error: {e}")
            send({"type": "idle"})
            time.sleep(1)

    logger.info("Yuki stopped.")
    send({"type": "idle"})


if __name__ == "__main__":
    run()
