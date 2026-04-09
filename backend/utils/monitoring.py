import psutil
import time

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
            "timestamp": time.time()
        }
    except Exception as e:
        return {"error": str(e)}
