import os
from datetime import datetime
import schedule
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from backend.speech.recognition import recognize_speech
from backend.speech.synthesis import speak
from backend.utils.logger import get_logger

logger = get_logger(__name__)

class TaskScheduler:
    def __init__(self):
        self.chrome_base_dir = os.path.expanduser("~\\AppData\\Local\\Google\\Chrome\\User Data")
        self.profiles = self._get_chrome_profiles()

    def _get_chrome_profiles(self):
        """Get list of available Chrome profiles"""
        profiles = {}
        try:
            base_dir = self.chrome_base_dir
            for item in os.listdir(base_dir):
                if item.startswith('Profile '):
                    # Get profile name from Preferences file if it exists
                    pref_path = os.path.join(base_dir, item, 'Preferences')
                    if os.path.exists(pref_path):
                        profiles[item] = item  # You could parse Preferences file for actual profile names
        except Exception as e:
            logger.error(f"Error reading Chrome profiles: {e}")
        return profiles

    def get_voice_input(self, prompt: str) -> str:
        """Get voice input with confirmation"""
        speak(prompt)
        while True:
            text = recognize_speech()
            if not text:
                speak("I didn't catch that, please try again")
                continue
            
            speak(f"I heard: {text}. Is that correct? Say yes or no.")
            confirmation = recognize_speech()
            if confirmation and "yes" in confirmation.lower():
                return text.lower().strip()
            speak("Let's try again.")

    def get_chrome_profile(self):
        """Interactively get Chrome profile choice"""
        if not self.profiles:
            speak("No Chrome profiles found. Using default profile.")
            return "Default"

        speak("Which Chrome profile should I use? I found these profiles:")
        for profile in self.profiles.keys():
            speak(profile.replace("Profile ", "Profile "))
        
        profile_input = self.get_voice_input("Please say the profile number you want to use")
        
        # Try to match input to profile
        try:
            profile_num = int(''.join(filter(str.isdigit, profile_input)))
            profile_name = f"Profile {profile_num}"
            if profile_name in self.profiles:
                return profile_name
        except ValueError:
            pass
        
        speak("Profile not found. Using default profile.")
        return "Default"

    def schedule_slack_message(self):
        """Interactive Slack message scheduling"""
        # Get Chrome profile first
        profile = self.get_chrome_profile()
        
        # Get scheduling details
        time_str = self.get_voice_input("What time should I schedule the message for?")
        try:
            time_obj = datetime.strptime(time_str, "%I %p")
            formatted_time = time_obj.strftime("%H:%M")
        except ValueError:
            speak("Sorry, I couldn't understand the time format")
            return

        channel = self.get_voice_input("Which Slack channel should I send to?")
        message = self.get_voice_input("What message would you like me to send?")

        def send_slack_message():
            try:
                options = webdriver.ChromeOptions()
                options.add_argument(f'--profile-directory={profile}')
                options.add_argument(f'user-data-dir={self.chrome_base_dir}')
                
                driver = webdriver.Chrome(
                    service=Service(ChromeDriverManager().install()),
                    options=options
                )
                
                # Navigate to Slack
                driver.get("https://slack.com/app")
                
                # Wait for and click channel
                channel_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, f"//span[contains(text(), '{channel}')]"))
                )
                channel_button.click()
                
                # Send message
                msg_input = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[data-qa="message_input"]'))
                )
                msg_input.send_keys(message)
                msg_input.send_keys(u'\ue007')
                
                time.sleep(2)
                driver.quit()
                
            except Exception as e:
                error_msg = f"Error sending Slack message: {str(e)}"
                logger.error(error_msg)
                speak(error_msg)

        # Schedule task
        schedule.every().day.at(formatted_time).do(send_slack_message)
        speak(f"Message scheduled for {time_str} in channel {channel} using Chrome {profile}")