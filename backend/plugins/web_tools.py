"""
Web Tools Plugin — HTTP requests and UI design generation.
"""

import json
from backend.plugins._base import Plugin
from backend.utils.logger import get_logger
from backend.config import cfg

logger = get_logger(__name__)

class HttpGetPlugin(Plugin):
    name = "http_get"
    description = "Fetch data from URL (JSON/text)."
    parameters = {
        "url": {"type": "string", "description": "The URL to fetch", "required": True}
    }

    def execute(self, url: str = "", **_) -> str:
        if not url: return "No URL provided."
        try:
            import requests
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                return f"Request failed with status: {resp.status_code}"
            
            # If it's JSON, pretty print it, otherwise return snippet
            try:
                data = resp.json()
                return json.dumps(data, indent=2)[:3000]
            except:
                return resp.text[:3000]
        except Exception as e:
            return f"HTTP Get failed: {e}"
