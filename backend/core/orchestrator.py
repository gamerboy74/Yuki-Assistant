import asyncio
import json
import os
import re
import time
import audioop
import numpy as np
from typing import AsyncGenerator, Callable
from backend.utils.logger import get_logger
from backend.config import cfg
from backend.speech.sentinel import VoiceSentinel, VADStreamProcessor
from backend.speech.recognition import AsyncWhisperStreamer
from backend.speech.wake_word import WakeWordDetector
from backend.brain import process_stream
from backend.speech.synthesis_kokoro import HPVoiceSwitcher
from backend.proactive_agent import ProactiveAgent
from backend import executor

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
        self.use_elevenlabs_tts = bool(
            os.environ.get("ELEVENLABS_API_KEY") and os.environ.get("ELEVENLABS_VOICE_ID")
        )
        if self.use_elevenlabs_tts:
            logger.info("TTS provider: ElevenLabs (with local fallback)")
        else:
            logger.info("TTS provider: Local Kokoro/Edge (ElevenLabs keys not fully configured)")
        
        # Internal state
        self.running = False
        self.mode = "idle" # "idle" (wake word) or "active" (VAD)
        self.is_speaking = False
        self.stop_playback_event = asyncio.Event()
        self.wake_event = asyncio.Event()
        self.turn_lock = asyncio.Lock()
        self._mixer_ready = False
        self._brain_audio_buffer = bytearray()
        self._event_seq = 0
        self._turn_counter = 0
        self.active_mode_timeout_sec = float(
            cfg.get("assistant", {}).get("active_timeout_sec") or 
            os.environ.get("YUKI_ACTIVE_MODE_TIMEOUT_SEC", "8")
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
        def sync_speak(msg):
            if self.loop:
                self.loop.call_soon_threadsafe(lambda: asyncio.create_task(self._speak_alert(msg)))
        
        self.proactive = ProactiveAgent(speak_fn=sync_speak, send_fn=self._emit)

        # Buffers
        self.audio_buffer = bytearray()
        self.recording = False

    def _new_turn_id(self) -> str:
        self._turn_counter += 1
        return f"turn-{self._turn_counter:06d}"

    def _emit(self, event_type: str, *, turn_id: str | None = None, **payload):
        """Emit ordered UI event metadata to keep frontend state machine in sync."""
        # ── Optimization: IPC Telemetry Batching ──
        # Certain high-frequency/non-critical updates are de-prioritized to keep pipes clear.
        self._event_seq += 1
        msg = {
            "type": event_type,
            "seq": self._event_seq,
            "ts": time.time(),
            **payload,
        }
        if turn_id:
            msg["turn_id"] = turn_id
        
        # Immediate dispatch for core voice state events
        core_events = ("wake", "listening", "processing", "response", "speaking", "transcript", "idle")
        if event_type in core_events:
             self.send(msg)
        else:
            # For logs and loading, we can batch or just let it through if it's not spamming.
            # Currently just passing through but flagged for future batching.
            self.send(msg)

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
        
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self.sentinel.load())
            tg.create_task(self.stt.load())
            tg.create_task(self.voice_switcher.load())
            tg.create_task(self.proactive.start_async())
            
        elapsed = time.perf_counter() - start_time
        logger.info(f"Neural pipelines online in {elapsed:.2f}s.")
        self._log("All neural links established.")
            
        # ── Step 2: Launch background capture and logic loops ──
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
                            ack = "Yes boss?"
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
                and (time.time() - self._active_since) >= self.active_mode_timeout_sec
            ):
                self.mode = "idle"
                self._emit("idle")
                continue

            # 1. Direct Barge-In Check (VAD Confidence based)
            if self.is_speaking:
                confidence = self.sentinel.get_speech_confidence(chunk)
                if confidence > 0.7: 
                    logger.info("[ORCHESTRATOR] Speech detected during playback. Interrupting...")
                    self._log("Barge-in detected: Interrupting playback.")
                    self.stop_playback_event.set()
            
            # 2. VAD State Machine
            event = self.vad_processor.process_chunk(chunk)
            
            if event == "speech_start":
                self.recording = True
                self.audio_buffer = bytearray()
                self._active_since = time.time()
                self._emit("listening")
                
            if self.recording:
                self.audio_buffer.extend(chunk)
                
            if event == "speech_end":
                self.recording = False
                turn_id = self._new_turn_id()
                self._emit("processing", turn_id=turn_id)
                asyncio.create_task(self._process_turn(bytes(self.audio_buffer), turn_id))
                self.audio_buffer = bytearray()

    async def _process_turn(self, audio_data: bytes, turn_id: str):
        """Handles a single interaction turn."""
        async with self.turn_lock:
            try:
                # A. STT
                transcript = await self.stt.transcribe_bytes(audio_data)
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
        self._emit("processing", turn_id=turn_id)

        async with self.turn_lock:
            try:
                await self._process_transcript(transcript, turn_id, emit_transcript=False)
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
        
        self.recording = False
        self.audio_buffer = bytearray()
        self._active_since = 0.0
        self.mode = "idle"
        self._emit("idle")

    async def _process_transcript(self, transcript: str, turn_id: str, *, emit_transcript: bool = True):
        """Run a text transcript through the brain and TTS output."""
        if emit_transcript:
            self._emit("transcript", turn_id=turn_id, text=transcript)
            self._log(f"Processing command: '{transcript}'")

        # Start parallel background synthesis and playback queues
        self.stop_playback_event.clear()
        self._synth_queue = asyncio.Queue()
        self._play_queue = asyncio.Queue()
        
        self._synth_task = asyncio.create_task(self._synth_worker(turn_id))
        self._playback_task = asyncio.create_task(self._audio_playback_worker(turn_id))
        
        has_native_audio = False
        async for event in self.brain_stream(transcript):
            if event["type"] == "audio_chunk":
                # Stream multimodal audio directly to synth queue
                has_native_audio = True
                await self._synth_queue.put({"type": "native", "data": event["value"]})
            elif event["type"] == "text_sentence":
                text = event["value"]
                # Only queue fallback TTS if we haven't seen native audio yet
                if not has_native_audio:
                    self._emit("partial-response", turn_id=turn_id, text=text)
                    await self._synth_queue.put({"type": "text", "data": text})
            elif event["type"] == "tool_start":
                self._emit("loading", turn_id=turn_id, text=f"{event['value']}...")
            elif event["type"] == "final_response":
                final_text = event["value"]
                action = event.get("action")
                
                if action and action.get("type") != "none":
                    # Run actual OS command
                    logger.info(f"Neural Trigger: {action['type']} | params: {action.get('params')}")
                    exec_result = await asyncio.to_thread(executor.execute, action)
                    
                    # Error Correction Loop:
                    # If executor returns an explicit message (like "I couldn't find that app"),
                    # we use that instead of the brain's optimistic prediction.
                    if exec_result and isinstance(exec_result, str):
                        final_text = exec_result
                
                self._emit("response", turn_id=turn_id, text=final_text)
        
        # Signal end of stream to synth worker
        await self._synth_queue.put(None)
        
        # We NO LONGER await playback here. Releasing the lock allows 
        # the next turn to start thinking while this one is still talking.
        self.loop.create_task(self._await_turn_cleanup(self._synth_task, self._playback_task, turn_id))

    async def _await_turn_cleanup(self, synth_task, playback_task, turn_id: str):
        """Background cleanup for a completed turn's audio tasks."""
        await synth_task
        await playback_task
        
        # Emitting these here ensures visually that Yuki stays 'speaking' 
        # until the audio ends, even though the Thinking Lock was released early.
        self.mode = "idle"
        self._emit("turn_completed", turn_id=turn_id)
        self._emit("idle", turn_id=turn_id)
        
        logger.debug(f"Turn {turn_id} cleanup complete.")

    def _extract_inline_command(self, transcript: str) -> str:
        """Return text after wake phrase, or empty string when user said only wake word."""
        if not transcript:
            return ""

        lowered = transcript.lower()
        wake_words = sorted(self.wake_detector.wake_words, key=len, reverse=True)

        for wake in wake_words:
            idx = lowered.find(wake)
            if idx == -1:
                continue
            tail = transcript[idx + len(wake):]
            cleaned = re.sub(r"^[\s,.:;!?\-]+", "", tail).strip()
            return cleaned

        return ""

    def _ensure_mixer(self):
        """Initialize pygame mixer with universal standard settings (44.1kHz Stereo)."""
        if self._mixer_ready:
            return

        import pygame
        if not pygame.mixer.get_init():
            # 44100Hz Stereo is the gold standard for compatibility with MP3 and Synthesis.
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=4096)
        
        self._mixer_ready = True

    async def _synth_worker(self, turn_id: str):
        """Pre-fetches text from the brain and synthesizes it to files in parallel with playback."""
        try:
            from backend.speech import synthesis as cloud_tts
            while True:
                item = await self._synth_queue.get()
                if item is None:
                    # Signal EOF to playback queue
                    await self._play_queue.put(None)
                    break
                    
                if self.stop_playback_event.is_set():
                    continue

                if item["type"] == "native":
                    await self._play_queue.put(item)
                elif item["type"] == "text":
                    text = item["data"]
                    if self.use_elevenlabs_tts:
                        try:
                            # Pre-fetch cloud TTS to a file
                            file_path = await cloud_tts.synthesize_to_file_async(text)
                            if file_path:
                                await self._play_queue.put({"type": "file", "data": file_path})
                                continue
                        except Exception as e:
                            logger.warning(f"Synth failed, falling back to local: {e}")
                            self._log("Neural TTS failed — using local voice fallback.")
                    
                    # Local Kokoro generator doesn't do files right now, 
                    # so we just push the text to be rendered inline.
                    await self._play_queue.put({"type": "text_local", "data": text})

        except Exception as e:
            logger.error(f"Synth worker failed: {e}")
            await self._play_queue.put(None)

    async def _audio_playback_worker(self, turn_id: str):
        """Background task that pulls synthesized audio chunks/files and plays zero-gap."""
        try:
            while True:
                item = await self._play_queue.get()
                if item is None:
                    break
                    
                if self.stop_playback_event.is_set():
                    if item["type"] == "file":
                        try: os.unlink(item["data"])
                        except: pass
                    continue
                
                if not self.is_speaking:
                    self.is_speaking = True
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
            if self.is_speaking:
                self.is_speaking = False
                # We don't necessarily go to 'idle' here, the turn manager handles that
                # but we can send a hint or just let the finally block in _process_turn do it.

    async def _play_file_with_interrupt(self, path: str):
        """Play an mp3/wav file via pygame, yielding to asyncio loop allowing interrupt checks."""
        try:
            import pygame
            self._ensure_mixer()
            
            # Neural Pre-warm to close the latency gap
            import numpy as np
            pre_warm_samples = int(44100 * 0.15)
            silence = np.zeros((pre_warm_samples, 2), dtype=np.int16)
            pygame.mixer.Sound(buffer=silence).play()

            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
            
            while pygame.mixer.music.get_busy():
                if self.stop_playback_event.is_set():
                    pygame.mixer.music.stop()
                    break
                await asyncio.sleep(0.01)
        except Exception as e:
            logger.error(f"Play file failed: {e}")

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
            
            sound = pygame.mixer.Sound(buffer=resampled.tobytes())
            channel = sound.play()
            while channel.get_busy():
                if self.stop_playback_event.is_set():
                    channel.stop()
                    break
                await asyncio.sleep(0.01)
        except Exception as e:
            logger.error(f"Native chunk playback failed: {e}")

    async def _speak_alert(self, text: str):
        """Dedicated immediate playback path for proactive agent alerts."""
        try:
            self._emit("speaking")
            from backend.speech import synthesis as cloud_tts
            if self.use_elevenlabs_tts:
                path = await cloud_tts.synthesize_to_file_async(text)
                if path:
                    await self._play_file_with_interrupt(path)
                    try: os.unlink(path)
                    except: pass
                    return
            await self._speak_local_with_interrupt(text)
        except Exception as e:
            logger.error(f"Alert speak failed: {e}")

    async def _speak_local_with_interrupt(self, text: str, turn_id: str | None = None):
        """Plays local TTS (Kokoro/Edge) handling interruptions."""
        try:
            import pygame
            self._ensure_mixer()
            
            audio_chunks = []
            async for chunk in self.voice_switcher.speak_stream(text):
                audio_chunks.append(chunk)
                if self.stop_playback_event.is_set():
                    break
            
            if not self.stop_playback_event.is_set() and audio_chunks:
                full_audio = b"".join(audio_chunks)
                sound = pygame.mixer.Sound(buffer=full_audio)
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

    async def speak(self, text: str):
        """Public entry point for triggering speech from external drivers (Assistant, triggers)."""
        await self._speak_alert(text)

    def stop(self):
        """Standard shutdown procedure."""
        self.running = False
        if hasattr(self, 'proactive'):
            self.proactive.stop()
        logger.info("Yuki Orchestrator stopped.")
