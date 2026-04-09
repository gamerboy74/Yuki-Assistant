"""
Vision Plugin — Allows Yuki to take a background screenshot and analyze it with OpenAI Vision.
"""

import os
import base64
import io
from backend.plugins._base import Plugin
from backend.utils.logger import get_logger
from backend.config import OPENAI_API_KEY

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
            "description": "If you need to click an element, describe it here. The plugin will return its exact (x, y) pixel coordinates on the screen.",
            "required": False,
        }
    }

    def execute(self, query: str = "Describe what is on my screen.", find_coordinates_of: str = "", **_) -> str:
        if not OPENAI_API_KEY:
            return "Vision requires the OpenAI API key, but it is not set."

        try:
            from PIL import ImageGrab
        except ImportError:
            return "Pillow library is missing. Install via: pip install Pillow"

        try:
            from openai import OpenAI
        except ImportError:
            return "OpenAI library is missing. Install via: pip install openai"

        try:
            # Take a screenshot
            logger.info("Taking background screenshot for Vision analysis...")
            screenshot = ImageGrab.grab()
            orig_width, orig_height = screenshot.size
            
            # Compress it to optimize token usage and latency
            max_size = (1280, 720)
            screenshot.thumbnail(max_size)
            scale_ratio_width = orig_width / screenshot.size[0]
            scale_ratio_height = orig_height / screenshot.size[1]

            buffered = io.BytesIO()
            screenshot.save(buffered, format="JPEG", quality=75)
            img_b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

            # Send to GPT-4o Vision
            client = OpenAI(api_key=OPENAI_API_KEY)
            
            vision_query = query
            if find_coordinates_of:
                vision_query = f"I need to click on '{find_coordinates_of}'. Reply ONLY with the estimated X, Y coordinates in the image provided (which has width {screenshot.size[0]} and height {screenshot.size[1]}), separated by a comma. E.g. '400, 250'. If not found, reply 'NOT_FOUND'."

            response = client.chat.completions.create(
                model="gpt-4o",  # gpt-4o is significantly better at coordinate math than mini
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": vision_query},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{img_b64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=250,
            )

            result = response.choices[0].message.content.strip()

            if find_coordinates_of and result != "NOT_FOUND":
                # Scale coordinates back up to original screen size
                try:
                    parts = result.split(',')
                    cx = int(parts[0].strip())
                    cy = int(parts[1].strip())
                    real_x = int(cx * scale_ratio_width)
                    real_y = int(cy * scale_ratio_height)
                    return f"Coordinates found: ({real_x}, {real_y})"
                except Exception:
                    return f"Could not find exact coordinates. Vision model returned: {result}"

            logger.info("[VISION] Screen analysis successful.")
            return result

        except Exception as e:
            logger.error(f"[VISION] Error: {e}")
            return f"Failed to analyze screen: {str(e)[:150]}"
