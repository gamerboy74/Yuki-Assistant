from backend.config import cfg
import json

print("Checking config keys for Neural Management:")
print(f"Gemini Key: {'SET' if cfg['gemini'].get('google_api_key') else 'MISSING'}")
print(f"OpenAI Key: {'SET' if cfg['openai'].get('openai_api_key') else 'MISSING'}")
print(f"ElevenLabs Key: {'SET' if cfg['tts'].get('elevenlabs_api_key') else 'MISSING'}")
print(f"ElevenLabs Voice: {'SET' if cfg['tts'].get('elevenlabs_voice_id') else 'MISSING'}")

# Dump current config for inspection
print("\nCurrent yuki.config.json on disk (via cfg object):")
print(json.dumps(cfg, indent=2))
