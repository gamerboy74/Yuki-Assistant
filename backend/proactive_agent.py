"""
Proactive Agent — Yuki's background monitoring brain.

Runs as a daemon thread alongside the main voice loop.
Checks system health and alerts the user WITHOUT needing a command.

Monitors:
  1. CPU load > 85% for 30s sustained
  2. RAM usage > 90%
  3. Battery < 15% and discharging
  4. Disk space < 5 GB free on C:

Alerts are spoken via Yuki's TTS and shown in the UI.
Cooldown: won't repeat the same alert for 5 minutes.
"""

import threading
import time
import datetime
from backend.utils.logger import get_logger
from backend import memory as mem

logger = get_logger(__name__)

# Seconds between each monitoring poll
POLL_INTERVAL  = 30

# Minimum seconds between repeating the same alert type
ALERT_COOLDOWN = 300  # 5 minutes

from backend.utils.monitoring import PSUTIL_AVAILABLE, psutil

class ProactiveAgent:
    """Background thread that monitors system health and fires Yuki alerts."""
    
    # 2 × 30s = 60s sustained before alerting
    CPU_SUSTAINED_POLLS = 2

    def __init__(self, fire_alert_fn):
        """
        Args:
            fire_alert_fn: Orchestrator function to handle UI + Speech thread-safely
        """
        self._fire_alert_callback = fire_alert_fn
        self._stop  = threading.Event()
        self._boot_complete = threading.Event()
        self._last_alert: dict[str, float] = {}   # alert_type → last_fired_timestamp
        self._thread: threading.Thread | None = None

        # Track CPU high samples (need sustained high load, not a spike)
        self._cpu_high_count = 0

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("[PROACTIVE] Background agent started (Waiting for BOOT).")

    def signal_boot_complete(self) -> None:
        """Called by orchestrator once all neural pipelines are ready."""
        self._boot_complete.set()
        logger.info("[PROACTIVE] System boot complete. Monitoring active.")

    async def start_async(self) -> None:
        """Async-friendly wrapper for modern orchestrators."""
        import asyncio
        await asyncio.to_thread(self.start)

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("[PROACTIVE] Background agent stopped.")

    # ── Internal ──────────────────────────────────────────────────────────────

    def _run(self) -> None:
        # ── BOOT GATE ──
        # Block until the full system (Whisper, Kokoro, etc.) is ready
        self._boot_complete.wait()

        while not self._stop.is_set():
            try:
                self._check_all()
            except Exception as e:
                logger.warning(f"[PROACTIVE] Monitor cycle error: {e}")
            self._stop.wait(POLL_INTERVAL)

    def _check_all(self) -> None:
        if not PSUTIL_AVAILABLE:
            logger.warning("[PROACTIVE] psutil not installed — monitoring disabled.")
            self._stop.set()
            return

        # ── 1. CPU ────────────────────────────────────────────────────────
        cpu = psutil.cpu_percent(interval=1)
        if cpu > 85:
            self._cpu_high_count += 1
        else:
            self._cpu_high_count = 0

        if self._cpu_high_count >= self.CPU_SUSTAINED_POLLS:
            self._fire_alert(
                "cpu",
                f"Sir, I'm noticing sustained high load. Your CPU is at {cpu:.0f}%. "
                "Shall I investigate the source of this strain for you?"
            )
            self._cpu_high_count = 0  # Reset after alerting

        # ── 2. RAM ────────────────────────────────────────────────────────
        vmem = psutil.virtual_memory()
        if vmem.percent > 90:
            self._fire_alert(
                "ram",
                f"Pardon the interruption, Sir, but your memory usage is at {vmem.percent:.0f}%. "
                "It might be prudent to close a few background applications."
            )

        # ── 3. Battery ────────────────────────────────────────────────────
        battery = psutil.sensors_battery()
        if battery and not battery.power_plugged:
            if battery.percent <= 10:
                self._fire_alert(
                    "battery_critical",
                    f"Sir, battery levels are critical at {battery.percent:.0f}%. "
                    "I strongly advise connecting to a power source immediately."
                )
            elif battery.percent <= 20:
                self._fire_alert(
                    "battery_low",
                    f"Sir, we're down to {battery.percent:.0f}% battery. "
                    "You might want to reach for a charger."
                )

        # ── 4. Disk ───────────────────────────────────────────────────────
        try:
            disk = psutil.disk_usage("C:\\")
            free_gb = disk.free / (1024 ** 3)
            if free_gb < 5:
                self._fire_alert(
                    "disk",
                    f"Sir, the primary drive is nearly at capacity. Only {free_gb:.1f} GB remaining. "
                    "Shall I help you identify some files to archive?"
                )
        except Exception:
            pass  # Non-fatal

        # ── 5. Reminders ──────────────────────────────────────────────────
        try:
            due = mem.get_due_reminders()
            for r in due:
                self._fire_alert(
                    f"reminder_{r['id']}",
                    f"Heads up! You asked me to remind you: {r['text']}"
                )
                mem.mark_reminder_done(r['id'])
        except Exception as e:
            logger.error(f"[PROACTIVE] Reminder check failed: {e}")

        # ── 6. Context Insights (Birthdays, etc.) ──────────────────────────
        # TODO: Implement local memory scanning for dates
        pass

        # ── 7. Behavioral Pattern Suggestions ─────────────────────────────────────
        # After 3+ sessions, Yuki notices habits and proactively offers them.
        try:
            from backend.brain import reasoning
            patterns = mem.get_patterns()
            suggestion = reasoning.get_proactive_suggestion(patterns)
            
            if suggestion:
                hour = datetime.datetime.now().hour
                # We use a combined key for habit cooldown to avoid spamming different habits
                self._fire_alert(f"habit_general_{hour}", suggestion)
        except Exception as e:
            logger.error(f"[PROACTIVE] Pattern suggestion failed: {e}")

    def _fire_alert(self, alert_type: str, message: str) -> None:
        """Fire an alert if the cooldown has elapsed."""
        now = time.time()
        last = self._last_alert.get(alert_type, 0)

        if now - last < ALERT_COOLDOWN:
            logger.debug(f"[PROACTIVE] Alert '{alert_type}' on cooldown.")
            return

        self._last_alert[alert_type] = now
        logger.info(f"[PROACTIVE] Triggering orchestrated alert: {alert_type}")

        # Delegate everything to the orchestrator for thread-safety
        self._fire_alert_callback(message)
