"""
backend/daemon.py — Yuki 2.0 Proactive Background Daemon

Runs in its own thread alongside the main assistant loop.
Monitors: battery, CPU, RAM, scheduled reminders, daily briefing.
Fires events through a shared queue back to assistant.py.
"""
import threading
import time
import datetime
import queue
from backend.utils.logger import get_logger
from backend.config import cfg

logger = get_logger(__name__)

_daemon_cfg = cfg.get("daemon", {})
_ENABLED       = _daemon_cfg.get("enabled", True)
_BATT_WARN     = _daemon_cfg.get("battery_warn_pct", 20)
_CPU_WARN      = _daemon_cfg.get("cpu_warn_pct", 90)
_RAM_WARN      = _daemon_cfg.get("ram_warn_pct", 85)
_BRIEFING_HOUR = _daemon_cfg.get("briefing_hour", 9)

# Shared queue: daemon puts messages here, assistant.py reads them
event_queue: queue.Queue = queue.Queue()

# Track what we've already warned about (to avoid repeating)
_warned = {"battery": False, "cpu": False, "ram": False, "briefing_done": set()}
_cpu_high_since: float | None = None


def _put(text: str, speak: bool = True):
    """Push a proactive message to the main loop."""
    event_queue.put({"text": text, "speak": speak})
    logger.info(f"[Daemon] → {text!r}")


def _check_battery():
    global _warned
    try:
        import psutil
        b = psutil.sensors_battery()
        if not b:
            return
        pct = int(b.percent)
        if not b.power_plugged:
            if pct <= _BATT_WARN and not _warned["battery"]:
                _put(f"Battery sirf {pct}% reh gayi hai. Charger lagao jaldi!")
                _warned["battery"] = True
            elif pct > 30:
                _warned["battery"] = False   # Reset warning once charged
        else:
            _warned["battery"] = False
    except Exception as e:
        logger.debug(f"Battery check error: {e}")


def _check_cpu():
    global _cpu_high_since, _warned
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=1)
        if cpu >= _CPU_WARN:
            if _cpu_high_since is None:
                _cpu_high_since = time.time()
            elif time.time() - _cpu_high_since > 10 and not _warned["cpu"]:
                _put(f"CPU {cpu:.0f}% pe chal raha hai — kuch heavy lag raha hai.")
                _warned["cpu"] = True
        else:
            _cpu_high_since = None
            _warned["cpu"] = False
    except Exception as e:
        logger.debug(f"CPU check error: {e}")


def _check_ram():
    global _warned
    try:
        import psutil
        ram = psutil.virtual_memory().percent
        if ram >= _RAM_WARN and not _warned["ram"]:
            _put(f"RAM {ram:.0f}% use ho rahi hai. Kuch apps band karo?")
            _warned["ram"] = True
        elif ram < 75:
            _warned["ram"] = False
    except Exception as e:
        logger.debug(f"RAM check error: {e}")


def _check_briefing():
    """Fire once per day at the configured hour."""
    now = datetime.datetime.now()
    key = now.strftime("%Y-%m-%d")
    if now.hour == _BRIEFING_HOUR and key not in _warned["briefing_done"]:
        _warned["briefing_done"].add(key)
        # Build briefing: time + day greeting
        tod = "Subah" if now.hour < 12 else "Dopahar"
        day = now.strftime("%A")
        msg = f"{tod}! Aaj {day} hai. Koi kaam ho toh batao — main yahan hoon."
        _put(msg)


def _daemon_loop():
    """Main daemon loop — checks every 30 seconds."""
    logger.info("[Daemon] Started.")
    while True:
        try:
            _check_battery()
            _check_cpu()
            _check_ram()
            _check_briefing()
        except Exception as e:
            logger.error(f"[Daemon] Loop error: {e}")
        time.sleep(30)


def start() -> threading.Thread:
    """Start the daemon thread. Returns the thread object."""
    if not _ENABLED:
        logger.info("[Daemon] Disabled in config.")
        return None
    t = threading.Thread(target=_daemon_loop, daemon=True, name="YukiDaemon")
    t.start()
    return t
