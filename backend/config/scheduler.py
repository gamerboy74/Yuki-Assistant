import os

CHROME_PROFILE_DIR = os.path.expanduser("~\\AppData\\Local\\Google\\Chrome\\User Data")
CHROME_WORK_PROFILE = "Profile 1"  # Change if your work profile has a different name

SLACK_CONFIG = {
    "base_url": "https://slack.com/app",
    "retry_attempts": 3,
    "timeout": 10
}