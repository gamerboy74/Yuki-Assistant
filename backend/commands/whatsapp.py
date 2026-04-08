import pywhatkit
from backend.speech.synthesis import speak

def send_whatsapp(number: str, message: str):
    # number should include country code, e.g. "+919876543210"
    pywhatkit.sendwhatmsg_instantly(number, message)
    speak(f"Sent WhatsApp message to {number}")
