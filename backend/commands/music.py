import subprocess
import webbrowser
import time
import pyautogui
import keyboard
from backend.speech.synthesis import speak

def focus_spotify():
    """Return True if Spotify desktop is running & focused."""
    try:
        windows = pyautogui.getWindowsWithTitle('Spotify')
        if windows:
            windows[0].activate()
            return True
    except Exception:
        pass
    return False

def launch_spotify():
    """Open Spotify via its URI, falling back to exe if needed."""
    try:
        # This uses the OS‐registered handler for "spotify:"  
        os.startfile("spotify:")
    except OSError:
        # As a fallback, you can still try your explicit exe path
        spotify_path = r"C:\Program Files\WindowsApps\SpotifyAB.SpotifyMusic_1.268.528.0_x64__zpdnekdrzrea0\Spotify.exe"
        subprocess.Popen([spotify_path])
    speak("Opening Spotify")
    time.sleep(3)

def play_spotify(song: str = None):
    """
    Play `song` in desktop Spotify if available; otherwise
    toggle play/pause when no song, or fall back to web.
    """
    try:
        # Try desktop app first
        if not focus_spotify():
            launch_spotify()

        if song:
            time.sleep(0.5)
            keyboard.press_and_release('ctrl+l')   # focus search bar
            time.sleep(0.5)
            keyboard.write(song)
            time.sleep(0.5)
            keyboard.press_and_release('enter')    # select first result
            time.sleep(0.2)
            keyboard.press_and_release('enter')    # play it
            speak(f"Playing {song} on Spotify")
        else:
            # no song → toggle play/pause
            keyboard.press_and_release('space')
            speak("Toggled play/pause on Spotify")

    except Exception:
        # Fallback to web player
        query = song.strip().replace(" ", "%20") if song else ""
        web_url = f"https://open.spotify.com/search/{query}"
        webbrowser.open(web_url)
        speak(f"Opening Spotify Web to search for {song}")
        # give browser time to load
        time.sleep(8)
        pyautogui.click(x=500, y=500)
        time.sleep(0.5)
        pyautogui.hotkey('ctrl', 'k')
        time.sleep(2)
        pyautogui.write(song)
        time.sleep(4)
        pyautogui.hotkey('shift', 'enter')
        speak(f"Playing {song} on Spotify Web")

def play_youtube(song: str):
    """Open YouTube search results for `song` in the default browser."""
    query = song.strip().replace(" ", "+")
    url = f"https://www.youtube.com/results?search_query={query}"
    webbrowser.open(url)
    speak(f"Searching YouTube for {song}")

def toggle_play_pause():
    """Toggle play/pause in desktop Spotify."""
    if focus_spotify():
        keyboard.press_and_release('space')
        speak("Toggled play/pause")
    else:
        speak("Spotify is not running.")

def next_track():
    """Skip to next track in desktop Spotify."""
    if focus_spotify():
        keyboard.press_and_release('ctrl+right')
        speak("Skipping to next track")
    else:
        speak("Spotify is not running.")

def previous_track():
    """Go back to previous track in desktop Spotify."""
    if focus_spotify():
        keyboard.press_and_release('ctrl+left')
        speak("Going back to previous track")
    else:
        speak("Spotify is not running.")

def close_spotify():
    """Close Spotify desktop window (or Alt+F4 fallback)."""
    windows = pyautogui.getWindowsWithTitle('Spotify')
    if windows:
        windows[0].close()
        speak("Closing Spotify")
    else:
        keyboard.press_and_release('alt+f4')
        speak("Closing Spotify via Alt+F4")

def switch_browser_tab(direction: str = 'next'):
    """Switch browser tab: 'next' or 'prev'."""
    if direction == 'next':
        keyboard.press_and_release('ctrl+tab')
        speak("Switched to next tab")
    else:
        keyboard.press_and_release('ctrl+shift+tab')
        speak("Switched to previous tab")
