import asyncio
import time

def slow_tool(name, delay):
    print(f"Starting {name}...")
    time.sleep(delay)
    print(f"Finished {name}.")
    return f"{name} done"

async def test_parallel():
    print("Testing parallel tools...")
    start = time.time()
    
    # Simulate what I added to the brains
    tasks = [
        asyncio.to_thread(slow_tool, "Tool A", 2),
        asyncio.to_thread(slow_tool, "Tool B", 2),
    ]
    
    results = await asyncio.gather(*tasks)
    
    end = time.time()
    print(f"Results: {results}")
    print(f"Total time: {end - start:.2f}s")
    
    if (end - start) < 3:
        print("SUCCESS: Tools ran in parallel!")
    else:
        print("FAILURE: Tools ran sequentially.")

if __name__ == "__main__":
    asyncio.run(test_parallel())
