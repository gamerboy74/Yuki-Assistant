try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False

import time
from backend.config import cfg
from backend.utils.logger import get_logger

logger = get_logger(__name__)

def get_system_stats():
    """Returns a dictionary of current system performance metrics."""
    # Metadata - Respect the Dashboard selection (available even without psutil)
    provider = cfg.get("brain", {}).get("provider", "gemini").lower()
    if provider == "openai":
        ai_model = f"OpenAI ({cfg.get('openai', {}).get('model', 'gpt-4o-mini')})"
    elif provider == "ollama":
        ai_model = f"Ollama ({cfg.get('ollama', {}).get('model', 'mistral')})"
    else:
        ai_model = f"Gemini ({cfg.get('gemini', {}).get('model', '2.0-flash')})"

    if not PSUTIL_AVAILABLE:
        return {
            "cpu": 0,
            "ram": 0,
            "battery": {"percent": 100, "charging": True},
            "network": {"sent": 0, "recv": 0},
            "ai_model": ai_model,
            "timestamp": time.time(),
            "warning": "psutil not installed"
        }

    try:
        # CPU
        cpu_usage = psutil.cpu_percent(interval=None)
        
        # RAM
        ram = psutil.virtual_memory()
        ram_usage = ram.percent
        
        # Battery (if available)
        battery = psutil.sensors_battery()
        battery_pct = battery.percent if battery else None
        is_charging = battery.power_plugged if battery else None
        
        # Network (sent/recv bytes since last call)
        net = psutil.net_io_counters()
             
        return {
            "cpu": cpu_usage,
            "ram": ram_usage,
            "battery": {
                "percent": battery_pct,
                "charging": is_charging
            },
            "network": {
                "sent": net.bytes_sent,
                "recv": net.bytes_recv
            },
            "ai_model": ai_model,
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"Monitoring error: {e}")
        return {"error": str(e), "ai_model": ai_model}
