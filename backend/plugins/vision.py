import os
import io
from backend.plugins._base import Plugin
from backend.utils.logger import get_logger

logger = get_logger(__name__)

class VisionPlugin(Plugin):
    name = ""
    description = "Analyze current screen or OCR/Find coordinates."
    parameters = {
        "operation": {
            "type": "string",
            "description": "Task: 'analyze' (OCR/Analysis) or 'screenshot' (Save to Desktop)",
            "required": True,
        },
        "query": {
            "type": "string",
            "description": "What to look for or analyze in the screenshot (for 'analyze')",
            "required": False,
        },
        "find_coordinates_of": {
            "type": "string",
            "description": "Describe element to find (for 'analyze').",
            "required": False,
        }
    }

    _client = None

    def _get_client(self):
        """Persistent client handle for Gemini Vision."""
        if self._client is None:
            try:
                from google import genai
                from backend.config import cfg
                key_info = cfg.get("gemini", {}).get("google_ai_studio", {})
                api_key = key_info.get("api_key") or os.environ.get("GOOGLE_API_KEY")
                if not api_key:
                    return None
                from google.genai import types
                self._client = genai.Client(api_key=api_key)
            except ImportError as e:
                logger.error(f"[VISION] Required library missing: {e}")
                return None
        return self._client

    def execute(self, operation: str = "analyze", query: str = "Describe the screen.", find_coordinates_of: str = "", **_) -> str:
        if operation == "screenshot":
            return self._take_screenshot()
        return self._analyze_screen(query, find_coordinates_of)

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

    def _analyze_screen(self, query: str, find_coordinates_of: str) -> str:
        client = self._get_client()
        if not client:
            return "Vision requires the GOOGLE_API_KEY and 'google-genai' library."

        try:
            from PIL import ImageGrab
            from google.genai import types
        except ImportError as e:
            return f"Required library missing: {e}."

        try:
            # 1. Capture Screenshot
            logger.info("[VISION] Capturing background screenshot...")
            screenshot = ImageGrab.grab()
            orig_width, orig_height = screenshot.size
            
            # 2. Optimized size (Gemini is fast, but 720p is usually enough for UI detection)
            max_size = (1280, 720)
            screenshot.thumbnail(max_size)
            scale_ratio_width = orig_width / screenshot.size[0]
            scale_ratio_height = orig_height / screenshot.size[1]

            buffered = io.BytesIO()
            screenshot.save(buffered, format="JPEG", quality=75)
            img_bytes = buffered.getvalue()

            # 3. Analyze with Gemini 3 Flash
            # Client is already initialized in _get_client()
            
            vision_query = query
            if find_coordinates_of:
                # Optimized prompt for Gemini's spatial reasoning
                vision_query = (
                    f"Task: Find the exact center coordinates of '{find_coordinates_of}' on this screen. "
                    f"Screen dimensions: {screenshot.size[0]}x{screenshot.size[1]}. "
                    "Reply ONLY with the coordinates in format 'X, Y'. "
                    "Example: '450, 220'. If not found, reply 'NOT_FOUND'."
                )

            response = client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part(text=vision_query),
                            types.Part(inline_data=types.Blob(mime_type="image/jpeg", data=img_bytes))
                        ]
                    )
                ]
            )

            result = response.text.strip()

            # 4. Handle Coordinate Logic
            if find_coordinates_of and "NOT_FOUND" not in result:
                try:
                    import re
                    match = re.search(r"(\d+)\s*,\s*(\d+)", result)
                    if match:
                        cx = int(match.group(1))
                        cy = int(match.group(2))
                        real_x = int(cx * scale_ratio_width)
                        real_y = int(cy * scale_ratio_height)
                        logger.info(f"[VISION] Coordinate detected: {real_x}, {real_y}")
                        return f"Coordinates found: ({real_x}, {real_y})"
                except Exception:
                    pass

            logger.info("[VISION] Screen analysis successful.")
            return result

        except Exception as e:
            logger.error(f"[VISION] Error: {e}")
            return f"Failed to analyze screen: {str(e)[:150]}"

class AnalyzeScreenPlugin(VisionPlugin):
    name = "analyze_screen"
    description = "Analyze screen and answer questions."
    parameters = {"query": {"type": "string", "description": "Question about screen", "required": True}}
    def execute(self, query: str = "", **params) -> str:
        return self._analyze_screen(query, params.get("find_coordinates_of", ""))

class ScreenshotPlugin(VisionPlugin):
    name = "screenshot"
    description = "Save screenshot to Desktop."
    parameters = {}
    def execute(self, **params) -> str:
        return self._take_screenshot()
