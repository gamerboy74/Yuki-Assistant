import asyncio
import json
import os
import re
import time

import numpy as np
from typing import AsyncGenerator, Callable
from backend.utils.logger import get_logger
from backend.config import cfg
from backend.speech.sentinel import VoiceSentinel, VADStreamProcessor
from backend.speech.recognition import AsyncWhisperStreamer
from backend.speech.wake_word import WakeWordDetector
from backend.brain import process_stream
from backend.utils.audio_duck import duck, unduck
from backend.speech.synthesis_kokoro import HPVoiceSwitcher
from backend.proactive_agent import ProactiveAgent
from backend import executor
from backend.utils.tokens import calculate_cost

logger = get_logger(__name__)

class YukiOrchestrator:
    """
    High-Performance Async Orchestrator for Yuki.
    Handles concurrent streams for zero-latency interaction.
    """
    def __init__(self, send_fn: Callable[[dict], None]):
        self.send = send_fn
        self.sentinel = VoiceSentinel()
        self.vad_processor = VADStreamProcessor(self.sentinel)
        self.stt = AsyncWhisperStreamer()
        self.brain_stream = process_stream
        self.voice_switcher = HPVoiceSwitcher()
        self.wake_detector = WakeWordDetector()
        # Log initial TTS provider status
        if self._check_elevenlabs_ready():
            logger.info("TTS provider: ElevenLabs (with local fallback)")
        else:
            logger.info("TTS provider: Local Kokoro/Edge (ElevenLabs keys not fully configured)")
        
        # Internal state
        self.running = False
        self.mode = "idle" # "idle" (wake word) or "active" (VAD)
        self.is_speaking = False
        self._speaking_count = 0
        self.stop_playback_event = asyncio.Event()
        self._current_brain_task = None
        self._speech_streak = 0
        self._pause_gate = asyncio.Event()
        self._pause_gate.set() # Open by default
        self.is_verifying_interruption = False
        self._last_was_question = False
        self._is_text_turn = False  # True when turn originated from keyboard (not microphone)

        # Wire the orchestrator's stop event to synthesis.py's global stop mechanism
        import backend.speech.synthesis as _synth_module
        _synth_module.add_stop_condition(lambda: self.stop_playback_event.is_set())
        
        self.wake_event = asyncio.Event()

        self.turn_lock = asyncio.Lock()
        self._mixer_ready = False
        self._brain_audio_buffer = bytearray()
        self._event_seq = 0
        self._turn_counter = 0
        self.active_mode_timeout_sec = float(
            cfg.get("assistant", {}).get("active_timeout_sec") or 
            os.environ.get("YUKI_ACTIVE_MODE_TIMEOUT_SEC", "5")
        )
        self._active_since = 0.0
        self.loop = None
        
        # Expert Reliability: Health Tracking
        self._provider_health = {
            "gemini": {"fails": 0, "last_fail": 0},
            "openai": {"fails": 0, "last_fail": 0}
        }
        self._audio_queue = asyncio.Queue()
        self._playback_task = None
        
        # Proactive Agent (Autonomous Health)
        self.proactive = ProactiveAgent(
            fire_alert_fn=lambda msg: self.loop.call_soon_threadsafe(
                lambda: asyncio.create_task(self.fire_proactive_alert(msg))
            )
        )

        # Tokens & Cost Tracking
        self.session_usage = {
            "input": 0,
            "output": 0,
            "cached": 0,
            "cost": 0.0,
            "turns": 0
        }

        # Buffers
        self.audio_buffer = bytearray()
        self.recording = False
        self._proactive_lock = asyncio.Lock()
        self._confirmation_event = asyncio.Event()

    def signal_confirmation(self):
        """Called by IPC bridge when user clicks 'confirm' or verbally confirms."""
        self._confirmation_event.set()

    def _check_elevenlabs_ready(self) -> bool:
        """Check if ElevenLabs TTS is configured — checks config file AND env vars."""
        key = cfg.get("tts", {}).get("elevenlabs_api_key") or os.environ.get("ELEVENLABS_API_KEY", "")
        voice = cfg.get("tts", {}).get("elevenlabs_voice_id") or os.environ.get("ELEVENLABS_VOICE_ID", "")
        provider = cfg.get("tts", {}).get("provider", "elevenlabs").lower()
        return bool(key and voice and provider == "elevenlabs")

    @property
    def use_elevenlabs_tts(self) -> bool:
        """Dynamic property — always reflects live config state."""
        return self._check_elevenlabs_ready()

    def _new_turn_id(self) -> str:
        self._turn_counter += 1
        return f"turn-{self._turn_counter:06d}"

    def _emit(self, event_type: str, *, turn_id: str | None = None, **payload):
        """Emit UI event metadata to keep frontend state machine in sync."""
        msg = {
            "type": event_type,
            **payload,
        }
        if turn_id:
            msg["turn_id"] = turn_id
        
        # Dispatch immediately
        self.send(msg)

    def _emit_volume(self, chunk: bytes):
        """Calculates RMS volume and emits a normalized value (0.0 to 1.0) for UI sentient scaling."""
        try:
            # Expert: Vectorized root-mean-square for high efficiency
            data = np.frombuffer(chunk, dtype=np.int16)
            if len(data) == 0: return
            
            rms = np.sqrt(np.mean(np.square(data.astype(np.float32))))
            # Normalize: 32768 is max for int16, but speech peaks are usually around 10000-15000
            normalized = min(1.0, rms / 12000.0)
            if normalized > 0.01: # Noise floor
                self._emit("volume_update", volume=normalized)
        except Exception as e:
            logger.debug(f"Volume emit failed: {e}")

    def _log(self, text: str):
        """Send a real-time event log to the dashboard."""
        self._emit("log", text=text)
        logger.info(f"[HUD Log] {text}")

    async def start(self):
        """Start the main orchestrated loop with parallel neural warmup."""
        self.loop = asyncio.get_running_loop()
        self.running = True
        logger.info("Yuki High-Performance Orchestrator starting...")
        
        # ── Optimization: Parallel Neural Link-up ──
        # We load high-weight models (Whisper, Kokoro, Silero) in parallel.
        # This reduces the sequential boot time from ~14s down to the time of the slowest model load.
        start_time = time.perf_counter()
        self._log("Priming neural pipelines...")
        
        async def _safe_load(name: str, coro):
            try:
                await coro
                logger.info(f"[BOOT] {name} loaded successfully.")
            except Exception as e:
                logger.error(f"[BOOT] {name} failed to load: {e}. Continuing in degraded mode.")

        await asyncio.gather(
            _safe_load("Silero VAD", self.sentinel.load()),
            _safe_load("Whisper STT", self.stt.load()),
            _safe_load("Kokoro TTS", self.voice_switcher.load()),
            _safe_load("Proactive Agent", self.proactive.start_async()),
        )
            
        elapsed = time.perf_counter() - start_time
        logger.info(f"Neural pipelines online in {elapsed:.2f}s.")
        self._log("Neural links established (check logs for any degraded components).")

        # ── Step 2: Signal Proactive Agent to start monitoring ──
        # Now that synthesis engine is warmed up, it's safe to fire alerts.
        self.proactive.signal_boot_complete()
            
        # ── Step 3: Launch background capture and logic loops ──
        # We start these as background tasks and return. This allows the 
        # Assistant to proceed to the greeting as soon as initialization is done.
        input_queue = asyncio.Queue()
        self._capture_task = asyncio.create_task(self._input_stream_task(input_queue))
        self._logic_task = asyncio.create_task(self._main_logic_task(input_queue))
        
        logger.info("Yuki High-Performance Orchestrator ready.")

    async def _input_stream_task(self, queue: asyncio.Queue):
        """Dedicated task for lightning-fast audio capture."""
        import pyaudio
        pa = pyaudio.PyAudio()
        stream = pa.open(
            rate=16000,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=512
        )
        
        try:
            while self.running:
                # Use run_in_executor to not block the event loop with blocking read
                data = await asyncio.to_thread(stream.read, 512, exception_on_overflow=False)
                
                # --- ECHO GATE ---
                # Discard audio chunks if Yuki is currently speaking to prevent self-transcription
                if getattr(self, "is_speaking", False):
                    continue

                await queue.put(data)
        except Exception as e:
            logger.error(f"Input stream error: {e}")
        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()

    async def _main_logic_task(self, queue: asyncio.Queue):
        """Central logic: Idle -> Wake -> Active -> Idle."""
        while self.running:
            chunk = await queue.get()
            
            # --- IDLE MODE (Wake Word) ---
            if self.mode == "idle":
                event = self.vad_processor.process_chunk(chunk)

                if event == "speech_start":
                    self.recording = True
                    self.audio_buffer = bytearray()

                if self.recording:
                    self.audio_buffer.extend(chunk)

                if event == "speech_end":
                    self.recording = False
                    transcript = await self.stt.transcribe_bytes(bytes(self.audio_buffer))
                    text = (transcript or "").lower()
                    if any(w in text for w in self.wake_detector.wake_words):
                        self.mode = "active"
                        self._active_since = time.time()
                        self._emit("wake", text=transcript)
                        self._log(f"Wake word detected: '{transcript}'")

                        inline_cmd = self._extract_inline_command(transcript)
                        if inline_cmd:
                            # Wake + command in one shot: execute directly with no extra acknowledgement.
                            turn_id = self._new_turn_id()
                            self._emit("processing", turn_id=turn_id)
                            asyncio.create_task(self._process_inline_turn(inline_cmd, turn_id))
                        else:
                            # Wake only: audible confirmation so user knows Yuki is listening.
                            ack = self._get_acknowledgment()
                            self._emit("response", text=ack)
                            await self._speak_alert(ack)
                            self._emit("listening")
                    self.audio_buffer = bytearray()
                continue

            # --- ACTIVE MODE (VAD + Brain) ---
            if (
                self.mode == "active"
                and not self.recording
                and not self.is_speaking
                and not self.turn_lock.locked()
                and self._active_since > 0
                and (time.time() - self._active_since) >= self._get_current_timeout()
            ):
                self.mode = "idle"
                self._emit("idle")
                continue

            # 1. Smarter Barge-In Check (Neural Economy 2.0)
            if self.is_speaking:
                confidence = self.sentinel.get_speech_confidence(chunk)
                if confidence > 0.85: # High bar for interruption
                    self._speech_streak += 1
                else:
                    self._speech_streak = 0

                if self._speech_streak >= 3: # Must be sustained speech (approx 100ms)
                    logger.info("[ORCHESTRATOR] Sustained speech detected. Interrupting...")
                    self._log("Barge-in: Interrupting for new command.")
                    self.stop_playback_event.set()
                    self._speech_streak = 0
                    
                    # Pause the brain loop rather than killing it immediately
                    self._pause_gate.clear()
                    self.is_verifying_interruption = True
                    logger.debug("[ORCHESTRATOR] J.A.R.V.I.S. Protocol: Interaction paused for verification.")
            # 2. VAD State Machine
            event = self.vad_processor.process_chunk(chunk)
            
            if event == "speech_start":
                self.recording = True
                self.audio_buffer = bytearray()
                self._active_since = time.time()
                self._emit("listening")
                duck() # Dim music while listening to user
                
            if self.recording:
                self.audio_buffer.extend(chunk)
            
            if event == "speech_end":
                self.recording = False
                unduck() # Restore volume after user finished speaking
                turn_id = self._new_turn_id()
                self._emit("processing", turn_id=turn_id)
                
                # If we were in the middle of a response, this is a barge-in
                is_barge = self.is_speaking
                
                # Capture the current task to cancel it if needed
                prev_task = self._current_brain_task if is_barge else None
                
                self._current_brain_task = asyncio.create_task(
                    self._process_turn(bytes(self.audio_buffer), turn_id, is_barge=is_barge, previous_task=prev_task)
                )
                self.audio_buffer = bytearray()
                

    async def _process_turn(self, audio_data: bytes, turn_id: str, is_barge: bool = False, previous_task: asyncio.Task | None = None):
        """Handles a single interaction turn."""
        # 1. J.A.R.V.I.S. Protocol: Interruption Analysis
        if is_barge:
            try:
                transcript = await self.stt.transcribe_bytes(audio_data)
                clean_text = self._extract_inline_command(transcript)
                
                # Check for "Dismissal" or "Noise" (No command intent)
                is_dismissal = not clean_text or any(w in clean_text.lower() for w in ["no", "nevermind", "ignore", "sorry", "continue"])
                
                if is_dismissal:
                    logger.info(f"[ORCHESTRATOR] Interruption dismissed (transcript: '{clean_text}'). Resuming...")
                    # If there was speech but it was unclear, ask for clarification
                    if not clean_text and len(audio_data) > 3000: # Over ~200ms of audio
                        phrase = self._get_verification_phrase()
                        self._emit("response", text=phrase)
                        await self._speak_alert(phrase)
                    
                    self.is_verifying_interruption = False
                    self.stop_playback_event.clear()
                    self._pause_gate.set() # RESUME OLD TURN
                    self._emit("turn_completed", turn_id=turn_id)
                    return
                else:
                    # Verified Interrupt: User has a new command
                    logger.info(f"[ORCHESTRATOR] Verified interruption: '{clean_text}'. Terminating previous task.")
                    if previous_task and not previous_task.done():
                        previous_task.cancel()
                    
                    # Proceed to acquire turn lock and process as a new command
                    self.is_verifying_interruption = False
                    transcript = clean_text # Use the clean text for the new command
            except Exception as e:
                logger.error(f"Interruption logic failed: {e}")
                self._pause_gate.set() # Failsafe: resume
                return

        async with self.turn_lock:
            try:
                # If not already transcribed by barge-in logic
                if not is_barge:
                    transcript = await self.stt.transcribe_bytes(audio_data)
                    transcript = self._extract_inline_command(transcript)
                
                if not transcript:
                    self.mode = "idle"
                    self._emit("turn_completed", turn_id=turn_id)
                    self._emit("idle", turn_id=turn_id)
                    return

                await self._process_transcript(transcript, turn_id)
            except Exception as e:
                logger.error(f"Turn processing failed: {e}")
                self._emit("response", turn_id=turn_id, text="I hit a runtime issue, but I am still online.")
            finally:
                pass # Sync Alignment: reset events are now in _await_turn_cleanup

    async def _process_inline_turn(self, transcript: str, turn_id: str):
        """Run wake+inline command inside serialized turn lock."""
        async with self.turn_lock:
            try:
                await self._process_transcript(transcript, turn_id, emit_transcript=True)
            except Exception as e:
                logger.error(f"Inline turn failed: {e}")
                self._emit("response", turn_id=turn_id, text="I hit a runtime issue, but I am still online.")
            finally:
                pass # Sync alignment

    async def handle_text_input(self, text: str):
        """Process a typed text message from the UI as a normal turn."""
        transcript = (text or "").strip()
        if not transcript:
            return

        turn_id = self._new_turn_id()
        self.mode = "active"
        self._is_text_turn = True  # Smart isolation: flag as text turn → go idle after cleanup
        self._emit("processing", turn_id=turn_id)

        async with self.turn_lock:
            try:
                self._current_brain_task = asyncio.create_task(self._process_transcript(transcript, turn_id, emit_transcript=False))
                await self._current_brain_task
            except asyncio.CancelledError:
                logger.info(f"[ORCHESTRATOR] Text turn {turn_id} cancelled.")
            except Exception as e:
                logger.error(f"Text turn failed: {e}")
                self._emit("response", turn_id=turn_id, text="I hit a runtime issue, but I am still online.")
            finally:
                pass # Sync alignment

    async def handle_preview_voice(self, text: str, voice_id: str, provider: str):
        """Play a voice audition through the orchestrator's managed mixer."""
        logger.info(f"[ORCHESTRATOR] Preview requested: {voice_id} ({provider})")
        
        # 1. Stop any ongoing speech
        self.stop_playback_event.set()
        
        # Allow a tiny moment for workers to clear
        await asyncio.sleep(0.1)
        self.stop_playback_event.clear()
        
        self.is_speaking = True
        self._emit("speaking")
        
        try:
            from backend.speech import synthesis as cloud_tts
            # Generate the sample
            path = await cloud_tts.synthesize_to_file_async(text, voice_id=voice_id, provider=provider)
            if path:
                # Play it using the orchestrator's interruptible playback
                await self._play_file_with_interrupt(path)
                try: os.unlink(path)
                except: pass
            else:
                logger.error("Preview synthesis failed (no audio generated).")
        except Exception as e:
            logger.error(f"Preview handling failed: {e}")
        finally:
            self.is_speaking = False
            self._emit("idle")

    async def handle_manual_trigger(self):
        """Enter active listening mode from the UI trigger button."""
        self.mode = "active"
        self._active_since = time.time()
        self._emit("listening")

    async def handle_cancel_listening(self):
        """Cancel active listening mode and return to idle."""
        logger.info("[ORCHESTRATOR] Cancel requested. Stopping current activities.")
        
        # Stop any ongoing speech/playback
        self.stop_playback_event.set()
        
        if self.recording:
            self.recording = False
            unduck()
            
        self.audio_buffer = bytearray()
        self._active_since = 0.0
        self.mode = "idle"
        self._emit("idle")

    async def _process_transcript(self, transcript: str, turn_id: str, *, emit_transcript: bool = True):
        """Run a text transcript through the brain and TTS output."""
        if emit_transcript:
            self._emit("transcript", turn_id=turn_id, text=transcript)
            self._log(f"Processing command: '{transcript}'")

        # Conversational Turn Tracking: 1 user interaction = 1 turn
        self.session_usage["turns"] += 1

        # Start parallel background synthesis and playback queues
        self.stop_playback_event.clear()
        
        # Capture as locals so workers use THIS turn's queues, not self's (which may be replaced)
        synth_queue = asyncio.Queue()
        play_queue = asyncio.Queue()
        self._synth_queue = synth_queue
        self._play_queue = play_queue
        
        self._synth_task = asyncio.create_task(self._synth_worker(turn_id, synth_queue, play_queue))
        self._playback_task = asyncio.create_task(self._audio_playback_worker(turn_id, play_queue))
        
        has_native_audio = False
        async for event in self.brain_stream(transcript):
            # J.A.R.V.I.S Protocol: Pause point
            await self._pause_gate.wait()
            
            if event["type"] == "audio_chunk":
                # Stream multimodal audio directly to synth queue
                has_native_audio = True
                await synth_queue.put({"type": "native", "data": event["value"]})
            elif event["type"] == "text_sentence":
                text = event["value"]
                # Only queue fallback TTS if we haven't seen native audio yet
                if not has_native_audio:
                    self._emit("partial-response", turn_id=turn_id, text=text)
                    await synth_queue.put({"type": "text", "data": text})
            elif event["type"] == "usage":
                # Aggregate session tokens and cost
                m_input = event.get("input") or 0
                m_output = event.get("output") or 0
                m_cached = event.get("cached") or 0
                m_model = event.get("model", "gpt-4o-mini")
                
                cost = calculate_cost(m_model, m_input, m_output, m_cached)
                
                self.session_usage["input"] += m_input
                self.session_usage["output"] += m_output
                self.session_usage["cached"] = self.session_usage.get("cached", 0) + m_cached
                self.session_usage["cost"] += cost
                
                self._emit("usage_update", data=self.session_usage)
                logger.info(f"[ORCHESTRATOR] Session Usage Updated: {self.session_usage['input']} in (+{self.session_usage.get('cached', 0)} cached), {self.session_usage['output']} out. Total Cost: ${self.session_usage['cost']:.6f}")

            elif event["type"] == "tool_start":
                self._emit("loading", turn_id=turn_id, text=f"{event['value']}...")
            elif event["type"] == "final_response":
                final_text = event["value"]
                # Conversational Persistence: Track if Yuki asked a question
                self._last_was_question = final_text.strip().endswith("?")
                action = event.get("action")
                
                if action and action.get("type") != "none":
                    # Hardened Confirmation Layer for destructive plugins
                    exec_result = await self._execute_with_confirmation(action, turn_id)
                    
                    # Behavioral Learning: Track successful execution to learn user patterns
                    from backend.brain import reasoning
                    reasoning.track_execution(action["type"])
                    
                    # Error Correction Loop:
                    # If executor returns an explicit message (like "I couldn't find that app"),
                    # we use that instead of the brain's optimistic prediction.
                    if exec_result and isinstance(exec_result, str):
                        final_text = exec_result
                
                self._emit("response", turn_id=turn_id, text=final_text)
        
        # Signal end of stream to synth worker
        await synth_queue.put(None)
        
        # We NO LONGER await playback here. Releasing the lock allows 
        # the next turn to start thinking while this one is still talking.
        self.loop.create_task(self._await_turn_cleanup(self._synth_task, self._playback_task, turn_id))

    async def _await_turn_cleanup(self, synth_task, playback_task, turn_id: str):
        """Background cleanup for a completed turn's audio tasks."""
        try:
            # Shield worker checks to prevent re-await errors
            if synth_task and not synth_task.done():
                await synth_task
            if playback_task and not playback_task.done():
                await playback_task
        except asyncio.CancelledError:
            logger.debug(f"[ORCHESTRATOR] Turn {turn_id} workers were cancelled.")
        except Exception as e:
            logger.error(f"[ORCHESTRATOR] Cleanup failure for {turn_id}: {e}")
        finally:
            self._emit("turn_completed", turn_id=turn_id)

            # ── Smart Isolation: Listening vs Idle post-turn ──────────────────────
            # For text input turns: go straight to idle (user is at keyboard, not mic).
            # For voice turns where Yuki asked a question: stay in active listening.
            # For all other voice turns: go to idle (wake-word mode).
            is_text_turn = getattr(self, "_is_text_turn", False)
            self._is_text_turn = False  # Always reset flag

            if is_text_turn or not self._last_was_question:
                # Return to idle — either text turn or Yuki didn't ask a question
                self.mode = "idle"
                self._active_since = 0.0
                self._emit("idle", turn_id=turn_id)
                logger.debug(f"[ORCHESTRATOR] Turn {turn_id} complete → IDLE")
            else:
                # Yuki asked a question in voice mode — stay active for the follow-up
                self._active_since = time.time()
                self._emit("listening")
                logger.debug(f"[ORCHESTRATOR] Turn {turn_id} complete → LISTENING (question pending)")

            # Clear global references if THEY are the tasks that just finished
            if self._synth_task == synth_task: self._synth_task = None
            if self._playback_task == playback_task: self._playback_task = None

            if not self.is_verifying_interruption and not self.is_speaking:
                self.stop_playback_event.clear()

            logger.debug(f"Turn {turn_id} cleanup complete.")

    def _get_acknowledgment(self) -> str:
        """Returns a sophisticated, randomized professional acknowledgment."""
        import random
        hour = time.localtime().tm_hour
        
        # J.A.R.V.I.S. / F.R.I.D.A.Y. inspired banks
        if 5 <= hour < 12:
            morning_extra = ["The morning looks promising, Sir. ", "Starting the day, Sir? ", ""]
            bank = [f"{random.choice(morning_extra)}Listening.", "Online and ready, Sir.", "At your service.", "Yes, Sir?"]
        elif 22 <= hour or hour < 5:
            night_extra = ["Still working, Sir? ", "The world is quiet, Sir. ", ""]
            bank = [f"{random.choice(night_extra)}I'm here.", "Working late, Sir?", "Standing by.", "Yes, Sir?"]
        else:
            bank = ["At your service, Sir.", "Listening, Sir.", "Online and ready.", "Yes, Sir?", "Standing by.", "Always here, Sir."]
        
        return random.choice(bank)

    def _get_verification_phrase(self) -> str:
        """Returns a polite query to clarify if the user was interrupting intentionally."""
        import random
        bank = [
            "Sir, were you saying something?",
            "I'm sorry, Sir, did you have a request?",
            "Excuse me, Sir, did you need me?",
            "Sir, did you wish to interrupt?",
            "My apologies, Sir, I thought I heard you speak."
        ]
        return random.choice(bank)

    def _get_current_timeout(self) -> float:
        """Returns either standard timeout or an extended one if Yuki asked a question."""
        base = self.active_mode_timeout_sec
        if self._last_was_question:
            # Give significantly more time for answering a question (e.g. 20s)
            return base * 2.5 
        return base

    def _begin_speaking(self):
        """Reference-counted speaker gate opening."""
        self._speaking_count += 1
        self.is_speaking = True
        logger.debug(f"[GATE] Speaking count: {self._speaking_count} (Muted)")

    def _end_speaking(self):
        """Reference-counted speaker gate closing."""
        self._speaking_count = max(0, self._speaking_count - 1)
        if self._speaking_count == 0:
            self.is_speaking = False
            logger.debug("[GATE] Speaking count: 0 (Unmuted)")
        else:
            logger.debug(f"[GATE] Speaking count: {self._speaking_count} (Still Muted)")

    async def speak(self, text: str):
        """Public alias for internal speech alerts."""
        self._begin_speaking()
        duck()
        try:
            await self._speak_alert(text)
        finally:
            unduck()
            self._end_speaking()

    async def _execute_with_confirmation(self, action: dict, turn_id: str) -> str | None:
        """Determines if an action needs user approval and manages the timeout/UI interaction."""
        CONFIRM_REQUIRED_PLUGINS = {"file_ops", "email", "computer_hands", "system_control"}
        plugin_name = action.get("type")

        if plugin_name not in CONFIRM_REQUIRED_PLUGINS:
            # Low-risk action, execute immediately
            logger.info(f"Neural Trigger (Immediate): {plugin_name}")
            return await asyncio.to_thread(executor.execute, action, self.send)

        # High-risk action: Start the confirmation contract
        logger.warning(f"[SECURITY] Awaiting confirmation for: {plugin_name}")
        self._confirmation_event.clear()
        
        # 1. Prompt UI
        self._emit("awaiting_confirmation", turn_id=turn_id, action=action)
        
        # 2. Speak the prompt (Brain usually does this, but we ensure it's logged)
        self._log(f"Sir, I require your confirmation to execute: {plugin_name}.")
        
        try:
            # 3. Wait for UI signal with strict 10s timeout
            await asyncio.wait_for(self._confirmation_event.wait(), timeout=10.0)
            
            # 4. User confirmed
            logger.info(f"[SECURITY] User confirmed {plugin_name}. Executing...")
            return await asyncio.to_thread(executor.execute, action, self.send)
            
        except asyncio.TimeoutError:
            # 5. Safety Default: Auto-cancel on timeout
            logger.info(f"[SECURITY] Confirmation timeout for {plugin_name}. Action cancelled.")
            self._emit("response", turn_id=turn_id, text="Action cancelled due to timeout.")
            await self._speak_alert("Action cancelled.")
            return "Sir, I cancelled the action as you didn't confirm in time."
        except Exception as e:
            logger.error(f"Confirmation layer failure: {e}")
            return "Sir, something went wrong during the confirmation check."


    def _extract_inline_command(self, transcript: str) -> str:
        """
        Human-grade sanitation: Strips ALL instances of any wake-word plus 
        any leading phonetic stutters or punctuation.
        """
        if not transcript:
            return ""

        # 1. Phonetic De-stuttering (removes consecutive duplicate words like "Yuki Yuki" or "Hey Hey")
        words = transcript.split()
        if not words: return ""
        
        clean_words = [words[0]]
        for w in words[1:]:
            if w.lower() != clean_words[-1].lower():
                clean_words.append(w)
        
        sanitized = " ".join(clean_words)
        lowered = sanitized.lower()
        
        # 2. Aggressive Multi-Wake Stripping
        wake_words = sorted(self.wake_detector.wake_words, key=len, reverse=True)
        
        # Strip all occurrences of wake words from the start of the string
        changed = True
        while changed:
            changed = False
            for wake in wake_words:
                if lowered.startswith(wake.lower()):
                    sanitized = sanitized[len(wake):].strip(",. ")
                    lowered = sanitized.lower()
                    changed = True
                    break
        
        return sanitized.strip()

    def _ensure_mixer(self):
        """Initialize pygame mixer with universal standard settings (44.1kHz Stereo)."""
        if self._mixer_ready:
            return

        import pygame
        if not pygame.mixer.get_init():
            # 44100Hz Stereo is the gold standard for compatibility with MP3 and Synthesis.
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=4096)
        
        self._mixer_ready = True

    async def _synth_worker(self, turn_id: str, synth_queue: asyncio.Queue, play_queue: asyncio.Queue):
        """Pre-fetches text from the brain and synthesizes it to files in parallel with playback."""
        try:
            from backend.speech import synthesis as cloud_tts
            while True:
                item = await synth_queue.get()
                if item is None:
                    # Signal EOF to playback queue
                    await play_queue.put(None)
                    break
                    
                if self.stop_playback_event.is_set():
                    continue

                if item["type"] == "native":
                    await play_queue.put({"type": "native", "data": item["data"]})
                elif item["type"] == "text":
                    text = item["data"]
                    if self.use_elevenlabs_tts:
                        try:
                            # Pre-fetch cloud TTS to a file
                            file_path = await cloud_tts.synthesize_to_file_async(text)
                            if file_path:
                                await play_queue.put({"type": "file", "data": file_path})
                                continue
                        except Exception as e:
                            logger.warning(f"Synth failed, falling back to local: {e}")
                            self._log("Neural TTS failed — using local voice fallback.")
                    
                    # Local Kokoro generator doesn't do files right now, 
                    # so we just push the text to be rendered inline.
                    await play_queue.put({"type": "text_local", "data": text})

        except Exception as e:
            logger.error(f"Synth worker failed: {e}")
            await play_queue.put(None)

    async def _audio_playback_worker(self, turn_id: str, play_queue: asyncio.Queue):
        """Background task that pulls synthesized audio chunks/files and plays zero-gap."""
        try:
            while True:
                item = await play_queue.get()
                if item is None:
                    break
                    
                if self.stop_playback_event.is_set():
                    if item["type"] == "file":
                        try: os.unlink(item["data"])
                        except: pass
                    # CRITICAL: If interrupted, we must exit the loop immediately to trigger 
                    # the finally block and restore system volume/microphone gate.
                    break
                
                if not self.is_speaking:
                    self._begin_speaking()
                    duck()
                    self._emit("speaking", turn_id=turn_id)
                
                if item["type"] == "native":
                    await self._play_native_chunk(item["data"])
                elif item["type"] == "file":
                    file_path = item["data"]
                    await self._play_file_with_interrupt(file_path)
                    try: os.unlink(file_path)
                    except: pass
                elif item["type"] == "text_local":
                    # Kokoro streams directly
                    await self._speak_local_with_interrupt(item["data"], turn_id=turn_id)
        except Exception as e:
            logger.error(f"Audio playback worker failed: {e}")
        finally:
            if getattr(self, "is_speaking", False):
                unduck()
            self._end_speaking()
            # Turn manager (_await_turn_cleanup) handles idle/listening state transitions.

    async def _play_file_with_interrupt(self, path: str):
        """Play an mp3/wav file via unified synthesis playback."""
        import backend.speech.synthesis as _synth_module
        await _synth_module.play_audio_file_async(path)

    async def _play_native_chunk(self, chunk: bytes):
        """Fixes Gemini's 24kHz vs 16kHz pitch issue using high-speed numpy interpolation."""
        import pygame
        self._ensure_mixer()
        
        try:
            # ── Optimization: Numpy Vectorized Resampling ──
            # Much faster and cleaner than audioop on modern Python versions.
            audio_int16 = np.frombuffer(chunk, dtype=np.int16)
            
            # Target is 44.1kHz (Mixer standard), Source is 24kHz (Gemini)
            num_samples = len(audio_int16)
            new_num_samples = int(num_samples * 44100 / 24000)
            
            # Linear interpolation for speed (Zero-latency)
            resampled = np.interp(
                np.linspace(0, num_samples, new_num_samples, endpoint=False),
                np.arange(num_samples),
                audio_int16
            ).astype(np.int16)
            
            # --- FIXED: Mono to Stereo conversion ---
            # Pygame mixer is initialized to 2 channels. 
            # Playing 1D mono buffer to a 2D mixer makes it play 2x fast.
            resampled_stereo = np.column_stack((resampled, resampled))
            
            # Emit volume for reactive Orb
            self._emit_volume(resampled_stereo.tobytes())

            sound = pygame.mixer.Sound(buffer=resampled_stereo.tobytes())
            channel = sound.play()
            while channel.get_busy():
                if self.stop_playback_event.is_set():
                    channel.stop()
                    break
                await asyncio.sleep(0.01)
        except Exception as e:
            logger.error(f"Native chunk playback failed: {e}")

    async def fire_proactive_alert(self, message: str):
        """
        Main entry point for autonomous background alerts (Proactive Agent).
        These inject context into memory to keep the AI updated on system state.
        """
        await self._fire_system_alert(message, turn_id="proactive-alert", inject_memory=True)

    async def _speak_alert(self, text: str, turn_id: str = "system-alert"):
        """
        Standard system acknowledgments ("At your service", "Listening").
        Fires UI and Voice but does NOT inject into brain memory.
        """
        await self._fire_system_alert(text, turn_id=turn_id, inject_memory=False)

    async def _fire_system_alert(self, message: str, turn_id: str, inject_memory: bool = False):
        """
        Internal core for all system speech/UI events outside the main brain loop.
        Ensures thread-safe UI state transitions and synthesized voice.
        """
        async with self._proactive_lock:
            mode_before = self.mode
            self._begin_speaking()
            duck() 
            try:
                # 1. UI Event
                self._emit("speaking", turn_id=turn_id)
                prefix = "⚠️ " if inject_memory else "" # Add warning icon only for proactive alerts
                self._emit("response", turn_id=turn_id, text=f"{prefix}{message}")
                
                # 2. Voice Output
                from backend.speech import synthesis as cloud_tts
                if self.use_elevenlabs_tts:
                    path = await cloud_tts.synthesize_to_file_async(message)
                    if path:
                        await self._play_file_with_interrupt(path)
                        try: os.unlink(path)
                        except: pass
                    else:
                        await self._speak_local_with_interrupt(message, turn_id=turn_id)
                else:
                    await self._speak_local_with_interrupt(message, turn_id=turn_id)

                # 3. Memory Injection (Isolated from system acknowledgments)
                if inject_memory:
                    from backend.brain import shared
                    shared.add_assistant_message(f"[Proactive] {message}")

                # 4. Mode Logic
                is_question = message.strip().endswith("?")
                if is_question:
                    self.mode = "active"
                    self._active_since = time.monotonic()
                    logger.info(f"[{turn_id.upper()}] Question detected. Entering active listener window.")
                elif mode_before == "idle":
                    self.mode = "idle"
                    self._emit("idle")
                    self._active_since = 0.0

                # 5. Autonomous Recovery Logic (Only for RAM/Health messages)
                if inject_memory and "ram" in message.lower():
                    from backend.plugins import browser as browser_mod
                    if browser_mod._failure_count < browser_mod._CIRCUIT_LIMIT:
                        logger.info("[ORCHESTRATOR] Autonomous RAM recovery triggered.")
                        try:
                            from backend.plugins.browser import BrowserHygienePlugin
                            hygiene = BrowserHygienePlugin()
                            res = await asyncio.to_thread(hygiene.execute)
                            logger.info(f"[ORCHESTRATOR] RAM Recovery Result: {res}")
                            self._log(f"Autonomous memory cleanup complete: {res}")
                        except Exception as he:
                            logger.error(f"Autonomous RAM recovery failed: {he}")
                    else:
                        logger.warning("[ORCHESTRATOR] Autonomous RAM recovery skipped: Browser circuit breaker open.")

            except Exception as e:
                logger.error(f"[ORCHESTRATOR] System alert failed: {e}")
            finally:
                self._emit("idle", turn_id=turn_id)
                if getattr(self, "is_speaking", False):
                    unduck()
                self._end_speaking()
                logger.info(f"[{turn_id.upper()}] Alert finished: {message[:30]}...")

    async def _speak_local_with_interrupt(self, text: str, turn_id: str | None = None):
        """Plays local TTS (Kokoro/Edge) handling interruptions."""
        try:
            import pygame
            import numpy as np
            self._ensure_mixer()
            
            audio_chunks = []
            async for chunk in self.voice_switcher.speak_stream(text):
                audio_chunks.append(chunk)
                if self.stop_playback_event.is_set():
                    break
            
            if not self.stop_playback_event.is_set() and audio_chunks:
                full_audio = b"".join(audio_chunks)
                
                # Resample from Kokoro's native 24kHz to mixer's 44.1kHz
                # Same pattern used in _play_native_chunk for Gemini audio
                audio_int16 = np.frombuffer(full_audio, dtype=np.int16)
                num_samples = len(audio_int16)
                new_num_samples = int(num_samples * 44100 / 24000)
                resampled = np.interp(
                    np.linspace(0, num_samples, new_num_samples, endpoint=False),
                    np.arange(num_samples),
                    audio_int16
                ).astype(np.int16)
                
                # --- FIXED: Mono to Stereo conversion ---
                resampled_stereo = np.column_stack((resampled, resampled))
                
                # Emit volume for reactive Orb scaling
                self._emit_volume(resampled_stereo.tobytes())
                
                sound = pygame.mixer.Sound(buffer=resampled_stereo.tobytes())
                channel = sound.play()
                
                while channel.get_busy():
                    if self.stop_playback_event.is_set():
                        channel.stop()
                        break
                    await asyncio.sleep(0.01)
        except Exception as local_err:
            logger.error(f"Local TTS path failed: {local_err}")

    def reload_config(self):
        """Live reload system parameters from the global cfg singleton."""
        from backend.config import cfg
        msg = "Hot-reloading system configuration..."
        logger.info(f"[ORCHESTRATOR] {msg}")
        self._log(msg)
        
        # 1. Update Wake Words
        new_wake = cfg.get("assistant", {}).get("wake_words", [])
        if new_wake:
            self.wake_detector.wake_words = new_wake
            logger.info(f" -> Wake words updated: {new_wake}")
            
        # 2. Update VAD Threshold
        new_vad = cfg.get("vad", {}).get("speech_threshold", 0.65)
        self.sentinel.threshold = min(max(new_vad, 0.1), 0.95)
        logger.info(f" -> VAD threshold updated: {self.sentinel.threshold:.2f}")

        # 3. Update Whisper Settings if changed (model reload is more heavy)
        new_whisper_size = cfg.get("whisper", {}).get("model_size", "base")
        if self.stt.model_size != new_whisper_size:
            logger.info(f" -> Whisper model change detected: {new_whisper_size}. Reloading...")
            self.stt.model_size = new_whisper_size
            try:
                self.stt.reload_model()
            except Exception as e:
                logger.error(f"Whisper reload failed: {e}")

    def stop(self):
        """Standard shutdown procedure."""
        self.running = False
        if hasattr(self, 'proactive'):
            self.proactive.stop()
        logger.info("Yuki Orchestrator stopped.")
