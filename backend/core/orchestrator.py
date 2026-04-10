import asyncio
import json
import os
import re
import time
import audioop
from typing import AsyncGenerator, Callable
from backend.utils.logger import get_logger
from backend.speech.sentinel import VoiceSentinel, VADStreamProcessor
from backend.speech.recognition import AsyncWhisperStreamer
from backend.speech.wake_word import WakeWordDetector
from backend.brain import process_stream
from backend.speech.synthesis_kokoro import HPVoiceSwitcher
from backend.proactive_agent import ProactiveAgent

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
        self.active_mode_timeout_sec = float(os.environ.get("YUKI_ACTIVE_MODE_TIMEOUT_SEC", "8"))
        self._active_since = 0.0
        
        # Expert Reliability: Health Tracking
        self._provider_health = {
            "gemini": {"fails": 0, "last_fail": 0},
            "openai": {"fails": 0, "last_fail": 0}
        }
        self._audio_queue = asyncio.Queue()
        self._playback_task = None
        
        # Proactive Agent (Autonomous Health)
        def sync_speak(msg):
            asyncio.run_coroutine_threadsafe(self._speak_with_interrupt(msg), asyncio.get_event_loop())
        
        self.proactive = ProactiveAgent(speak_fn=sync_speak, send_fn=self._emit)

        # Buffers
        self.audio_buffer = bytearray()
        self.recording = False

    def _new_turn_id(self) -> str:
        self._turn_counter += 1
        return f"turn-{self._turn_counter:06d}"

    def _emit(self, event_type: str, *, turn_id: str | None = None, **payload):
        """Emit ordered UI event metadata to keep frontend state machine in sync."""
        self._event_seq += 1
        msg = {
            "type": event_type,
            "seq": self._event_seq,
            "ts": time.time(),
            **payload,
        }
        if turn_id:
            msg["turn_id"] = turn_id
        self.send(msg)

    async def start(self):
        """Start the main orchestrated loop."""
        self.running = True
        logger.info("Yuki High-Performance Orchestrator started.")
        
        # Start Proactive Agent
        self.proactive.start()

        # Start PyAudio input stream task
        input_queue = asyncio.Queue()
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self._input_stream_task(input_queue))
            tg.create_task(self._main_logic_task(input_queue))

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
                            await self._speak_with_interrupt(ack)
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
                if confidence > 0.8: 
                    logger.info("[ORCHESTRATOR] Speech detected during playback. Interrupting...")
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
                self.mode = "idle"
                self._emit("turn_completed", turn_id=turn_id)
                self._emit("idle", turn_id=turn_id)

    async def _process_inline_turn(self, transcript: str, turn_id: str):
        """Run wake+inline command inside serialized turn lock."""
        async with self.turn_lock:
            try:
                await self._process_transcript(transcript, turn_id, emit_transcript=True)
            except Exception as e:
                logger.error(f"Inline turn failed: {e}")
                self._emit("response", turn_id=turn_id, text="I hit a runtime issue, but I am still online.")
            finally:
                self.mode = "idle"
                self._emit("turn_completed", turn_id=turn_id)
                self._emit("idle", turn_id=turn_id)

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
                self.mode = "idle"
                self._emit("turn_completed", turn_id=turn_id)
                self._emit("idle", turn_id=turn_id)

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

        # Start background playback loop
        self.stop_playback_event.clear()
        self._audio_queue = asyncio.Queue()
        self._playback_task = asyncio.create_task(self._audio_playback_worker(turn_id))
        
        has_native_audio = False
        async for event in self.brain_stream(transcript):
            if event["type"] == "audio_chunk":
                # Stream multimodal audio to queue immediately
                has_native_audio = True
                await self._audio_queue.put({"type": "native", "data": event["value"]})
            elif event["type"] == "text_sentence":
                text = event["value"]
                # Only queue fallback TTS if we haven't seen native audio yet
                if not has_native_audio:
                    await self._audio_queue.put({"type": "text", "data": text})
            elif event["type"] == "tool_start":
                self._emit("loading", turn_id=turn_id, text=f"{event['value']}...")
            elif event["type"] == "final_response":
                final_text = event["value"]
                self._emit("response", turn_id=turn_id, text=final_text)
        
        # Signal end of stream to playback worker
        await self._audio_queue.put(None)
        await self._playback_task

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

    async def _audio_playback_worker(self, turn_id: str):
        """Background task that consumes audio/text chunks and plays them sequentially."""
        try:
            while True:
                item = await self._audio_queue.get()
                if item is None:
                    break
                if self.stop_playback_event.is_set():
                    continue # Drain queue if interrupted
                
                if item["type"] == "native":
                    await self._play_native_chunk(item["data"])
                elif item["type"] == "text":
                    await self._speak_with_interrupt(item["data"], turn_id=turn_id)
        except Exception as e:
            logger.error(f"Audio playback worker failed: {e}")
        finally:
            self.is_speaking = False

    async def _play_native_chunk(self, chunk: bytes):
        """Fixes Gemini's 24kHz vs 16kHz pitch issue and plays a raw chunk."""
        import pygame
        self._ensure_mixer()
        
        try:
            # Resample 24k (Gemini) -> 44100k (Universal Mixer)
            import audioop
            # Note: We now output 2 channels (Stereo) for the 44100 mixer.
            resampled, _ = audioop.ratecv(chunk, 2, 1, 24000, 44100, None)
            
            # If mixer is stereo but source is mono, pygame needs it explicitly or 
            # we need to double the samples. SDL usually handles this if channels=2 was set in init.
            sound = pygame.mixer.Sound(buffer=resampled)
            channel = sound.play()
            while channel.get_busy():
                if self.stop_playback_event.is_set():
                    channel.stop()
                    break
                await asyncio.sleep(0.01)
        except Exception as e:
            logger.error(f"Native chunk playback failed: {e}")

    async def _speak_with_interrupt(self, text: str, turn_id: str | None = None):
        """Plays text fallback (Cloud/Local) but lets VAD stop it halfway."""
        # 1. Cloud: Premium Cloud (ElevenLabs)
        if self.use_elevenlabs_tts:
            try:
                from backend.speech import synthesis as cloud_tts
                speak_task = asyncio.create_task(asyncio.to_thread(cloud_tts.speak, text))
                while not speak_task.done():
                    await asyncio.sleep(0.05)
                    if self.stop_playback_event.is_set():
                        await asyncio.to_thread(cloud_tts.stop_speech)
                        break
                await speak_task
                return
            except Exception as e:
                logger.warning(f"ElevenLabs failed: {e}. Falling back to Local.")

        # 2. Local: Tertiary Local HP (Kokoro or Edge-TTS)
        try:
            import pygame
            self._ensure_mixer()
            
            audio_chunks = []
            async for chunk in self.voice_switcher.speak_stream(text):
                audio_chunks.append(chunk)
                if self.stop_playback_event.is_set():
                    break
            
            if not self.stop_playback_event.is_set():
                full_audio = b"".join(audio_chunks)
                sound = pygame.mixer.Sound(buffer=full_audio)
                channel = sound.play()
                
                while channel.get_busy():
                    if self.stop_playback_event.is_set():
                        channel.stop()
                        break
                    await asyncio.sleep(0.01)
        except Exception as local_err:
            logger.error(f"All TTS paths failed: {local_err}")

    def stop(self):
        """Standard shutdown procedure."""
        self.running = False
        if hasattr(self, 'proactive'):
            self.proactive.stop()
        logger.info("Yuki Orchestrator stopped.")
