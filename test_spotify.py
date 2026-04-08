import os
import time
import ctypes

def test_media_play():
    # 1. Open track
    os.startfile("spotify:track:5LGGHwSU3ZiUvMzPXSluK8")
    time.sleep(3.5)
    
    # 2. Simulate hardware Media Play/Pause key (0xB3)
    # KEYEVENTF_EXTENDEDKEY = 0x0001
    # KEYEVENTF_KEYUP       = 0x0002
    ctypes.windll.user32.keybd_event(0xB3, 0, 0x0001, 0)
    time.sleep(0.05)
    ctypes.windll.user32.keybd_event(0xB3, 0, 0x0001 | 0x0002, 0)
    print("Media Play sent.")

if __name__ == "__main__":
    test_media_play()
