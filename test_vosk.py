import vosk
import pyaudio
import json
import traceback
import sys
import os

# Add background to path to import local modules
sys.path.append(os.path.join(os.getcwd(), 'backend'))
from utils.audio_filters import AudioProcessor

vosk.SetLogLevel(-1)
print("Loading model...")
model = vosk.Model(lang="en-us")

# 1. Grammar Constraints
wake_words = ["yuki", "hey yuki", "ok yuki", "yukhi", "youki"]
grammar = json.dumps(wake_words + ["[unk]"])
rec = vosk.KaldiRecognizer(model, 16000, grammar)

# 2. Processor
processor = AudioProcessor()
sensitivity = 0.6

pa = pyaudio.PyAudio()
stream = pa.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=1024)

print(f"Listening for wake words: {wake_words}")
print("Gating active. Speak louder than your fan noise...")
stream.start_stream()

try:
    while True:
        data = stream.read(512, exception_on_overflow=False)
        if len(data) == 0:
            continue
            
        # Update floor
        processor.update_noise_floor(data)
        
        # Gate
        if not processor.is_speech(data, sensitivity=sensitivity):
            # Print noise floor occasionally
            if hash(data) % 100 == 0:
                print(f"Floor: {processor._noise_floor:.1f}", end="\r")
            continue

        if rec.AcceptWaveform(data):
            res = json.loads(rec.Result())
            text = res.get("text", "").lower()
            if text and text != "[unk]":
                print(f"\n[MATCH] {text}")
        else:
            res = json.loads(rec.PartialResult())
            text = res.get("partial", "").lower()
            if text and text != "[unk]":
                print(f"Partial: {text}", end="\r")

except KeyboardInterrupt:
    print("\nStopped.")
except Exception as e:
    traceback.print_exc()
finally:
    stream.stop_stream()
    stream.close()
    pa.terminate()
