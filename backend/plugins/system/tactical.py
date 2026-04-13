import os
import psutil
import datetime
from backend.plugins._base import Plugin
from backend import memory as mem
from backend.plugins.weather import WeatherPlugin
from backend.utils.logger import get_logger

logger = get_logger(__name__)

class TacticalReportPlugin(Plugin):
    name = "tactical_report"
    description = "Get a comprehensive JARVIS-style status report (System, Weather, Reminders)."
    parameters = {}

    def execute(self, **_) -> str:
        """
        Gathers: 
        1. System Stats (Battery, CPU, RAM)
        2. Weather (from existing WeatherPlugin)
        3. Due/Upcoming Reminders
        4. Current Time/Date
        """
        report = []
        
        # 1. System Info
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        battery = psutil.sensors_battery()
        bat_str = f"{battery.percent}% {'(Charging)' if battery.power_plugged else ''}" if battery else "Unknown"
        report.append(f"[SYSTEM] CPU: {cpu}% | RAM: {ram}% | Battery: {bat_str}")
        
        # 2. Time/Date
        now = datetime.datetime.now()
        report.append(f"[CHRONOS] {now.strftime('%I:%M %p, %A %B %d')}")
        
        # 3. Weather
        try:
            user_loc = mem.get_user().get("location", "Bhubaneswar")
            wp = WeatherPlugin()
            weather = wp.execute(city=user_loc)
            report.append(f"[METEOROLOGY] {weather}")
        except Exception:
            report.append("[METEOROLOGY] Sensor offline.")
            
        # 4. Reminders
        due = mem.get_due_reminders()
        if due:
            rem_list = ", ".join([r['text'] for r in due[:3]])
            report.append(f"[REMINDERS] Pending: {rem_list}")
        else:
            report.append("[REMINDERS] All clear.")
            
        return "\n".join(report)
