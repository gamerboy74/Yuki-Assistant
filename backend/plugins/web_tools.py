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

class DesignPlugin(Plugin):
    name = "design_web_page"
    description = "Generate UI/Web design (Tailwind/HTML)."
    parameters = {
        "content": {"type": "string", "description": "Description of the page or the raw code", "required": True},
        "path": {"type": "string", "description": "Slug for the page (e.g. 'landing_page')", "required": False}
    }

    def execute(self, content: str = "", path: str = "design", **_) -> str:
        # Standard Yuki design procedure: Save to 'designs/' and notify UI
        import os
        designs_dir = os.path.join(os.getcwd(), "designs")
        os.makedirs(designs_dir, exist_ok=True)
        
        filename = f"{path.strip().replace(' ', '_')}.html"
        full_path = os.path.join(designs_dir, filename)
        
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        logger.info(f"Design saved to {full_path}")
        return f"SUCCESS: Design generated and saved as '{filename}'. Sir, you can view it in the designs folder."
