import pygame
import time
import os

def test_audio():
    print("Initializing mixer at 22050Hz, Mono, 4096 buffer...")
    try:
        pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=4096)
        print("Mixer inited successfully.")
    except Exception as e:
        print(f"FAILED to init mixer: {e}")
        return

    # Try to play a simple beep or the test file
    test_file = "test.mp3"
    if not os.path.exists(test_file):
        print(f"Test file {test_file} not found. Creating a dummy sound...")
        # create a simple sine wave if possible, or just exit
        return

    print(f"Attempting to play {test_file}...")
    try:
        pygame.mixer.music.load(test_file)
        pygame.mixer.music.play()
        start = time.time()
        while pygame.mixer.music.get_busy() and time.time() - start < 5:
            time.sleep(0.1)
        print("Playback finished or timed out.")
    except Exception as e:
        print(f"Playback FAILED: {e}")
    finally:
        pygame.mixer.quit()

if __name__ == "__main__":
    test_audio()
