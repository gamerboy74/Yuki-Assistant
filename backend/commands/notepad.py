import subprocess
import time
import pyautogui
from backend.speech.synthesis import speak

def write_notepad(text: str):
    subprocess.Popen(["notepad.exe"])
    time.sleep(1)                 # wait for window
    pyautogui.write(text)
    speak("Typed into Notepad")
