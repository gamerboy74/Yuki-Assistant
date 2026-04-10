import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from backend.brain_gemini import process_stream

async def test_brain():
    print("Testing Gemini Async Stream...")
    try:
        # We just need to see if it starts without the "got generator" error
        gen = process_stream("Hello")
        # Just calling __anext__ once will trigger the code up to the first yield
        # which includes the await client.aio.models.generate_content_stream call.
        await gen.__anext__()
        print("VERIFICATION: Async iteration SUCCESS (neural link active).")
    except StopAsyncIteration:
        print("VERIFICATION: Async iteration finished normally.")
    except Exception as e:
        # If it says 'got generator', this will catch it
        print(f"VERIFICATION FAILURE: {e}")

if __name__ == "__main__":
    asyncio.run(test_brain())
