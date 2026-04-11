import os
import sys
from dotenv import load_dotenv

# Setup path
root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(root)

load_dotenv(os.path.join(root, ".env"), override=True)

from backend.config import cfg
from backend.brain_ollama import is_available, OLLAMA_BASE_URL, OLLAMA_MODEL

print(f"Testing connectivity to: {OLLAMA_BASE_URL} for model: {OLLAMA_MODEL}")
available = is_available()
print(f"Ollama Available: {available}")

if not available:
    import urllib.request
    import json
    try:
        url = f"{OLLAMA_BASE_URL}/api/tags"
        with urllib.request.urlopen(url, timeout=3) as resp:
            data = json.loads(resp.read())
            models = [m["name"] for m in data.get("models", [])]
            print(f"Found local models: {models}")
            print(f"Expecting startswith: {OLLAMA_MODEL.split(':')[0]}")
    except Exception as e:
        print(f"Low-level check failed: {e}")
