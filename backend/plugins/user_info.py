"""
User Info Plugin — Retrieve personal information and preferences from local memory.
"""

from backend.plugins._base import Plugin
from backend import memory as mem

class UserInfoPlugin(Plugin):
    name = "get_user_info"
    description = "Get user name/prefs from memory."
    parameters = {
        "query": {
            "type": "string",
            "description": "What to fetch: 'name', 'preferences', or 'all'",
            "required": True,
        }
    }

    def execute(self, query: str = "all", **_) -> str:
        user = mem.get_user()
        query = query.lower()
        
        if "name" in query:
            return f"Your name is {user['name']}." if user['name'] else "I don't know your name yet."
        elif "preference" in query or "like" in query:
            prefs = user.get("preferences", {})
            if prefs:
                return "Your preferences: " + ", ".join(f"{k} is {v}" for k,v in prefs.items())
            return "I don't have any preferences recorded for you yet."
            
        return mem.context_block()
