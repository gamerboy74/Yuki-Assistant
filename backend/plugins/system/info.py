"""
System Domain — Information
"""

import datetime
from backend.plugins._base import Plugin
from backend.utils.logger import get_logger

logger = get_logger(__name__)

class SystemInfoPlugin(Plugin):
    name = "system_info"
    description = "Get time, date, battery, or hardware info."
    parameters = {"query": {"type": "string", "description": "time, date, battery, cpu, ram", "required": True}}

    def execute(self, query: str = "time", **params) -> str:
        query = query.lower()
        now = datetime.datetime.now()
        
        try:
            if "time" in query:
                return f"The time is {now.strftime('%I:%M %p')}."
            if "date" in query:
                return f"Today is {now.strftime('%A, %B %d, %Y')}."
            if "battery" in query:
                import psutil
                batt = psutil.sensors_battery()
                if batt:
                    return f"Battery is at {batt.percent}% and {'charging' if batt.power_plugged else 'discharging'}."
                return "Battery information not available."
            return f"The current time is {now.strftime('%I:%M %p')}."
        except Exception as e:
            logger.error(f"[SYSTEM_INFO] Failed {query}: {e}")
            return "I couldn't retrieve that information."
