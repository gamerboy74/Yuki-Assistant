import asyncio
import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.speech.synthesis import preview_voice_async

async def test():
    print("Testing preview...")
    # en-US-GuyNeural is a known valid edge-tts voice
    await preview_voice_async("This is a test of the preview system.", "en-US-GuyNeural", "edge-tts")
    print("Done.")

if __name__ == "__main__":
    asyncio.run(test())
