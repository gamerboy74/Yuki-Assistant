import httpx
import time
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Cache settings
WEATHER_CACHE_DURATION = 1800  # 30 minutes
_weather_cache = {
    "data": None,
    "last_fetched": 0
}

# Global location cache to prevent ipapi.co 429 (Rate Limit) errors
_cached_location = None

async def get_weather_data():
    """Fetches weather data based on IP location if cache is expired."""
    global _cached_location
    now = time.time()
    if _weather_cache["data"] and (now - _weather_cache["last_fetched"]) < WEATHER_CACHE_DURATION:
        return _weather_cache["data"]

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 1. Get Location (Cached)
            if _cached_location is None:
                logger.info("[WEATHER] Fetching location from IP (First Run)...")
                loc_res = await client.get("https://ipapi.co/json/", follow_redirects=True)
                if loc_res.status_code != 200:
                    raise Exception(f"Location API failed with status {loc_res.status_code}")
                _cached_location = loc_res.json()
            
            loc_data = _cached_location
            lat = loc_data.get("latitude")
            lon = loc_data.get("longitude")
            city = loc_data.get("city", "Unknown")
            
            if lat is None or lon is None:
                raise Exception("Could not determine coordinates from IP")

            # 2. Get Weather via Open-Meteo
            logger.info(f"[WEATHER] Fetching weather for {city} ({lat}, {lon})...")
            weather_url = (
                f"https://api.open-meteo.com/v1/forecast?"
                f"latitude={lat}&longitude={lon}&current_weather=true"
                f"&hourly=uv_index,relative_humidity_2m&windspeed_unit=kmh"
            )
            
            weather_res = await client.get(weather_url)
            if weather_res.status_code != 200:
                raise Exception(f"Weather API failed with status {weather_res.status_code}")
            
            w_data = weather_res.json()
            current = w_data.get("current_weather", {})
            
            # Find the index for the current hour
            current_hour_iso = current.get("time")
            hourly_times = w_data.get("hourly", {}).get("time", [])
            h_idx = 0
            try:
                if current_hour_iso in hourly_times:
                    h_idx = hourly_times.index(current_hour_iso)
            except ValueError:
                pass

            humidity_list = w_data.get("hourly", {}).get("relative_humidity_2m", [])
            uv_list = w_data.get("hourly", {}).get("uv_index", [])
            
            humidity = 0
            uv_index = 0
            
            if h_idx < len(humidity_list):
                humidity = humidity_list[h_idx]
            else:
                humidity = humidity_list[0] if humidity_list else 0
                
            if h_idx < len(uv_list):
                uv_index = uv_list[h_idx]
            else:
                uv_index = uv_list[0] if uv_list else 0

            weather_obj = {
                "temp": current.get("temperature", 0),
                "wind": current.get("windspeed", 0),
                "humidity": humidity,
                "uv": uv_index,
                "city": city,
                "condition_code": current.get("weathercode", 0),
                "timestamp": now
            }
            
            _weather_cache["data"] = weather_obj
            _weather_cache["last_fetched"] = now
            logger.info(f"[WEATHER] Data updated: {city}, {weather_obj['temp']}°C")
            return weather_obj

    except Exception as e:
        logger.error(f"[WEATHER] Failed to fetch weather: {e}")
        # Return last cached value even if old, or None
        return _weather_cache["data"]
