"""
Quick test: verify all Yuki modules import and basic functions work.
Run from project root: .venv\Scripts\python test_yuki.py
"""
import sys
import os

# Make sure src/ is in path
SRC_DIR = os.path.join(os.path.dirname(__file__), "src")
sys.path.insert(0, SRC_DIR)

from dotenv import load_dotenv
load_dotenv(".env")

print("=" * 50)
print("  YUKI — Module Test")
print("=" * 50)

# Test 1: TTS
print("\n[1] Testing Text-to-Speech (edge-tts)...")
try:
    from yuki.speech.synthesis import speak
    print("    ✓ synthesis.py imported OK")
    print("    → Speaking test phrase...")
    speak("Yuki online. All systems go.")
    print("    ✓ TTS working")
except Exception as e:
    print(f"    ✗ TTS error: {e}")

# Test 2: Brain
print("\n[2] Testing Brain (OpenAI GPT-4o)...")
try:
    from yuki.brain import process
    print("    ✓ brain.py imported OK")
    result = process("What time is it?")
    print(f"    ✓ Brain response: {result}")
except Exception as e:
    print(f"    ✗ Brain error: {e}")

# Test 3: Executor
print("\n[3] Testing Executor (system_info)...")
try:
    from yuki.executor import execute
    print("    ✓ executor.py imported OK")
    info = execute({"type": "system_info", "params": {"query": "time"}})
    print(f"    ✓ System info: {info}")
except Exception as e:
    print(f"    ✗ Executor error: {e}")

# Test 4: Wake word detector
print("\n[4] Testing Wake Word (pvporcupine/STT)...")
try:
    from yuki.speech.wake_word import WakeWordDetector
    det = WakeWordDetector()
    print(f"    ✓ WakeWordDetector initialized (using porcupine: {det._use_porcupine})")
except Exception as e:
    print(f"    ✗ Wake word error: {e}")

print("\n" + "=" * 50)
print("  Test complete! Check above for any ✗ errors.")
print("=" * 50)
