"""Quick ElevenLabs diagnostic"""
import os, sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv('.env')

api_key  = os.environ.get('ELEVENLABS_API_KEY', '')
voice_id = os.environ.get('ELEVENLABS_VOICE_ID', 'cgSgspJ2msm6clMCkdW9')

print(f"API key  : {api_key[:12]}...{api_key[-4:] if len(api_key)>16 else '(short)'}")
print(f"Voice ID : {voice_id}")
print()

# Test 1: SDK import
print("Test 1 — SDK import:", end=' ')
try:
    from elevenlabs.client import ElevenLabs
    from elevenlabs import VoiceSettings
    print("OK")
except Exception as e:
    print(f"FAIL: {e}")
    sys.exit(1)

# Test 2: API connectivity
print("Test 2 — API call:", end=' ')
try:
    client = ElevenLabs(api_key=api_key)
    # List voices to test connectivity without consuming many chars
    voices = client.voices.get_all()
    print(f"OK — {len(voices.voices)} voices available")
except Exception as e:
    print(f"FAIL: {e}")
    sys.exit(1)

# Test 3: Actual TTS (short phrase)
print("Test 3 — TTS generate:", end=' ')
import tempfile, os as _os
try:
    audio = client.text_to_speech.convert(
        text="Test.",
        voice_id=voice_id,
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
    )
    chunks = list(audio)
    total = sum(len(c) for c in chunks)
    print(f"OK — {total} bytes generated")
except Exception as e:
    print(f"FAIL: {e}")
    # Try with default voice
    print("  Retrying with default voice (Aria)...", end=' ')
    try:
        audio = client.text_to_speech.convert(
            text="Test.",
            voice_id="cgSgspJ2msm6clMCkdW9",
            model_id="eleven_turbo_v2_5",
            output_format="mp3_44100_128",
        )
        chunks = list(audio)
        total = sum(len(c) for c in chunks)
        print(f"OK — {total} bytes — voice ID in .env may be wrong")
    except Exception as e2:
        print(f"FAIL: {e2}")

print()
print("Done.")
