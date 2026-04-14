"""Weather plugin — fetch weather via wttr.in (free, no API key)."""

from backend.plugins._base import Plugin
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class WeatherPlugin(Plugin):
    name = "get_weather"
    description = "Get the current weather for a city. Uses wttr.in — no API key needed."
    parameters = {
        "city": {
            "type": "string",
            "description": "City name. If omitted, I'll check my memory for your location.",
            "required": False,
        },
    }

    def execute(self, city: str = "", **_) -> str:
        if not city:
            from backend import memory as mem
            city = mem.get_user().get("location", "")
        
        if not city:
            return "Sir, which city's weather would you like? (I don't have your location in my memory records yet)."
        try:
            import requests
            import urllib.parse
            encoded = urllib.parse.quote(city)
            url = f"http://wttr.in/{encoded}?format=3"
            resp = requests.get(url, headers={"User-Agent": "curl/7.0"}, timeout=5)
            text = resp.text.strip()
            return text if text else f"Couldn't get weather for {city}."
        except Exception as e:
            logger.error(f"Weather error: {e}")
            return f"Couldn't fetch weather for {city}."
