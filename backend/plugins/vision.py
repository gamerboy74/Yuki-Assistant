import os
import io
from backend.plugins._base import Plugin
from backend.utils.logger import get_logger

logger = get_logger(__name__)

class VisionPlugin(Plugin):
    name = "analyze_screen"
    description = "Capture screen and analyze visual content (UI, errors, images) using Gemini Vision."
    parameters = {
        "operation": {
            "type": "string",
            "description": "Task: 'analyze' (describe screen) or 'screenshot' (save to Desktop)",
            "required": True,
            "enum": ["analyze", "screenshot"]
        },
        "query": {
            "type": "string",
            "description": "Specific question or element to look for (for 'analyze')",
            "required": False,
        }
    }

    _client = None

    def _get_client(self):
        if self._client is None:
            try:
                from google import genai
                from backend.config import cfg
                key_info = cfg.get("gemini", {}).get("google_ai_studio", {})
                api_key = key_info.get("api_key") or os.environ.get("GOOGLE_API_KEY")
                if not api_key: return None
                self._client = genai.Client(api_key=api_key)
            except ImportError: return None
        return self._client

    def execute(self, operation: str = "analyze", query: str = "Describe the screen.", **_) -> str:
        if operation == "screenshot": return self._take_screenshot()
        return self._analyze_screen(query)

    def _take_screenshot(self) -> str:
        try:
            from PIL import ImageGrab
            import datetime
            filename = f"screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            desktop = os.path.join(os.path.expanduser("~"), "Desktop", filename)
            screenshot = ImageGrab.grab()
            screenshot.save(desktop)
            return f"Screenshot saved to Desktop as {filename}."
        except Exception as e:
            return f"Screenshot failed: {e}"

    def _analyze_screen(self, query: str) -> str:
        client = self._get_client()
        if not client: return "Vision requires GOOGLE_API_KEY."
        
        try:
            from PIL import ImageGrab
            from google.genai import types
            screenshot = ImageGrab.grab()
            
            # Optimized size for Gemini
            max_size = (1280, 720)
            screenshot.thumbnail(max_size)
            buffered = io.BytesIO()
            screenshot.save(buffered, format="JPEG", quality=75)
            img_bytes = buffered.getvalue()

            # Internal: Force 1.5 Flash for high-speed OCR/Analysis
            response = client.models.generate_content(
                model="gemini-1.5-flash",
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part(text=query),
                            types.Part(inline_data=types.Blob(mime_type="image/jpeg", data=img_bytes))
                        ]
                    )
                ]
            )
            return response.text.strip()
        except Exception as e:
            logger.error(f"[VISION] {e}")
            return f"Analysis failed: {str(e)[:150]}"
