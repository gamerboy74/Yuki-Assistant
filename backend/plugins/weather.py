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
            "description": "City name, e.g. 'Mumbai', 'Delhi', 'New York'",
            "required": True,
        },
    }

    def execute(self, city: str = "", **_) -> str:
        if not city:
            return "Which city's weather would you like?"
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
