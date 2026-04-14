import sys
import os
from pathlib import Path

# Add project root to path
root = Path(r"c:\Users\gboy3\OneDrive\Documents\yuki_assistant")
sys.path.append(str(root))

try:
    from backend.brain.tools import get_all_plugins
    plugins = get_all_plugins()
    print(f"TOTAL PLUGINS REGISTERED: {len(plugins)}")
    print("-" * 30)
    for name in sorted(plugins.keys()):
        print(f" - {name}")
    print("-" * 30)
    
    if 13 <= len(plugins) <= 15:
        print("RESULT: SUCCESS (Consolidation Law Met)")
    else:
        print(f"RESULT: FAILURE (Count is {len(plugins)}, expected 13-15)")
except Exception as e:
    print(f"EROR DURING VERIFICATION: {e}")
