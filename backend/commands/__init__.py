from backend.intents.classifier import get_intent
from backend.commands.system import open_recycle_bin, delete_all_files
from backend.commands.music import play_spotify, play_youtube
from backend.commands.notepad import write_notepad
from backend.commands.whatsapp import send_whatsapp
from backend.commands.scheduler import TaskScheduler

_scheduler = TaskScheduler()

def handle_command(cmd: str):
    """Handle voice commands and route to appropriate functions"""
    cmd = cmd.lower().strip()
    
    # Add scheduling commands
    if any(word in cmd for word in ["schedule", "set up", "automate"]) and "slack" in cmd:
        _scheduler.schedule_slack_message()
        return
        
    # Music commands
    if cmd == "open spotify":
        play_spotify()
        return
    elif cmd.startswith("play "):
        song = cmd.replace("play ", "", 1).strip()
        # Handle "on spotify" suffix
        if "on spotify" in song:
            song = song.replace("on spotify", "").strip()
            play_spotify(song)
            return
        # Handle "on youtube" suffix
        elif "on youtube" in song:
            song = song.replace("on youtube", "").strip()
            play_youtube(song)
            return
        # Default to Spotify if no platform specified
        else:
            play_spotify(song)
            return
    
    # If not a direct command, try intent matching
    intent, params = get_intent(cmd)
    if not intent:
        speak("Sorry, I didn't understand that.")
        return

    # dispatch based on intent name
    if intent == "open_recycle_bin":
        return open_recycle_bin()
    if intent == "delete_all_files":
        return delete_all_files()
    if intent == "play_spotify":
        return play_spotify()
    if intent == "play_youtube":
        song = params.get("song", "")
        return play_youtube(song)
    if intent == "write_notepad":
        text = params.get("text", "")
        return write_notepad(text)
    if intent == "send_whatsapp":
        num = params.get("number", "")
        msg = params.get("message", "")
        return send_whatsapp(num, msg)

    # fallback (shouldn't hit this)
    speak("Sorry, something went wrong routing that command.")
