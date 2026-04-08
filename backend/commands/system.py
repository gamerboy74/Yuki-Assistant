import subprocess
import pyautogui
from backend.speech.synthesis import speak

def open_recycle_bin():
    """Open the Windows Recycle Bin folder."""
    subprocess.run(["explorer", "shell:RecycleBinFolder"])
    speak("Opened recycle bin")

def delete_all_files():
    """Select all files in the active window and delete them."""
    pyautogui.hotkey("ctrl", "a")
    pyautogui.press("delete")
    speak("Deleted all files")
