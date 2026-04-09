"""
Email Plugin — Drafts emails via the OS default email client (mailto: protocol).
"""

import os
import urllib.parse
from backend.plugins._base import Plugin
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class EmailPlugin(Plugin):
    name = "draft_email"
    description = "Draft an email to a recipient. Opens the default email application with the subject and body pre-filled so the user can review and send it."
    parameters = {
        "recipient": {
            "type": "string",
            "description": "Email address of the recipient (leave empty if unknown)",
        },
        "subject": {
            "type": "string",
            "description": "Subject line of the email",
            "required": True,
        },
        "body": {
            "type": "string",
            "description": "The full content of the email",
            "required": True,
        },
    }

    def execute(self, recipient: str = "", subject: str = "", body: str = "", **_) -> str:
        if not subject and not body:
            return "I need a subject or body to draft the email."

        try:
            # URI encode the components
            subject_encoded = urllib.parse.quote(subject)
            body_encoded = urllib.parse.quote(body)
            
            # Construct mailto URL
            mailto_url = f"mailto:{recipient}?subject={subject_encoded}&body={body_encoded}"
            
            # Open with default mail client
            os.startfile(mailto_url)
            
            logger.info(f"[EMAIL] Drafted email to {recipient or 'unknown'}")
            return "I've drafted the email for you to review and send."

        except Exception as e:
            logger.error(f"[EMAIL] Error: {e}")
            return f"Failed to draft email: {str(e)[:100]}"
