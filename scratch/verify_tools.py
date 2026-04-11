import os
import sys
from pathlib import Path

# Add backend to path
sys.path.append(os.getcwd())

from backend.tools.dispatcher import dispatch_tool

print("Testing type_text (simulated)...")
# Note: This will actually type wherever the cursor is! I'll use a very small string.
# res = dispatch_tool("type_text", {"text": "Yuki Test"})
# print(f"Result: {res}")

print("\nTesting open_file (simulated)...")
# I'll create a dummy file and try to open it.
user_home = Path(os.path.expanduser("~")).resolve()
yuki_saved = user_home / "Documents" / "Yuki_Saved"
yuki_saved.mkdir(parents=True, exist_ok=True)
test_file = yuki_saved / "yuki_test_dispatch.txt"

with open(test_file, "w") as f:
    f.write("Yuki is testing the dispatcher!")

res2 = dispatch_tool("open_file", {"path": "yuki_test_dispatch.txt"})
print(f"Result: {res2}")
