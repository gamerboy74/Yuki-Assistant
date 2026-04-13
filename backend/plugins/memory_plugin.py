"""
Memory Plugin — Direct interface to Yuki's neural facts and memories.
"""

from backend.plugins._base import Plugin
from backend import memory as mem

class SaveMemoryPlugin(Plugin):
    name = "save_memory"
    description = "Save a fact or information to remember for later."
    parameters = {
        "text": {
            "type": "string",
            "description": "The fact or information to remember (e.g., 'The anime website is anikai.to')",
            "required": True,
        }
    }

    def execute(self, text: str = "", **_) -> str:
        if not text: return "I didn't catch what you wanted me to remember, Sir."
        return mem.save_fact(text)

class RecallMemoryPlugin(Plugin):
    name = "recall_memory"
    description = "Search your memories for a specific fact or information."
    parameters = {
        "query": {
            "type": "string",
            "description": "Fuzzy search query (e.g., 'anime website')",
            "required": True,
        }
    }

    def execute(self, query: str = "", **_) -> str:
        if not query: return "Search query is empty."
        results = mem.recall(query, n=3)
        if not results:
            return f"I couldn't find any memories matching '{query}', Sir."
        
        resp = "Here is what I found in my neural links:\n"
        for i, r in enumerate(results, 1):
            resp += f"{i}. {r}\n"
        return resp

class ForgetAllMemoryPlugin(Plugin):
    name = "wipe_memories"
    description = "Clear all my memories and user profile data."
    parameters = {}

    def execute(self, **_) -> str:
        return mem.clear_all()
