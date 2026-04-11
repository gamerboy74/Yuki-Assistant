import psutil
import time
from backend.config import cfg

def get_system_stats():
    """Returns a dictionary of current system performance metrics."""
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
        
        # Metadata - Respect the Dashboard selection
        provider = cfg.get("brain", {}).get("provider", "gemini").lower()
        
        if provider == "openai":
            ai_model = f"OpenAI ({cfg.get('openai', {}).get('model', 'gpt-4o-mini')})"
        elif provider == "ollama":
            ai_model = f"Ollama ({cfg.get('ollama', {}).get('model', 'mistral')})"
        else:
            ai_model = f"Gemini ({cfg.get('gemini', {}).get('model', '2.0-flash')})"
             
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
        return {"error": str(e)}
