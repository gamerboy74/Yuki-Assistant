import os
import io
from backend.plugins._base import Plugin
from backend.utils.logger import get_logger

logger = get_logger(__name__)

class VisionPlugin(Plugin):
    name = "analyze_screen"
    description = "Take a screenshot of the user's current screen and answer a question about it. Examples: 'What am I looking at?', 'Explain this code', 'Summarize this page'."
    parameters = {
        "query": {
            "type": "string",
            "description": "What to look for or analyze in the screenshot",
            "required": True,
        },
        "find_coordinates_of": {
            "type": "string",
            "description": "If you need to click an element, describe it here. Returns exact (x, y) pixel coordinates.",
            "required": False,
        }
    }

    def execute(self, query: str = "Describe what is on my screen.", find_coordinates_of: str = "", **_) -> str:
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            return "Vision requires the GOOGLE_API_KEY, but it is not set."

        try:
            from PIL import ImageGrab
            from google import genai
            from google.genai import types
        except ImportError as e:
            return f"Required library missing: {e}. Install via: pip install Pillow google-genai"

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

            # 3. Analyze with Gemini 2.0 Flash
            client = genai.Client(api_key=api_key)
            
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
                model="gemini-2.0-flash",
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
                    # Look for the last 'X, Y' pattern in case Gemini rambles
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
