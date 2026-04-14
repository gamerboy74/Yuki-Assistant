"""
memory.py — Semantic Memory & User Knowledge
Consolidates memory_plugin and user_info features.
"""

from backend.plugins._base import Plugin
from backend import memory as mem
from backend.utils.logger import get_logger

logger = get_logger(__name__)

class MemoryPlugin(Plugin):
    name = "memory"
    description = """Manage Yuki's long-term memory and user profile.
Operations:
  save [fact: str] — store a new fact, preference, or event in long-term memory
  recall [query: str] — search memory for specific facts/preferences
  get_user — returns the full user profile (name, location, preferences, family)
  update_user [field: str, value: any] — update specific profile fields
  wipe [confirm: bool] — delete all memories (requires confirm=True)
"""
    parameters = {
        "operation": {
            "type": "string", "required": True,
            "enum": ["save", "recall", "get_user", "update_user", "wipe"]
        },
        "fact": {"type": "string", "description": "What to remember"},
        "query": {"type": "string", "description": "What to search for"},
        "field": {"type": "string", "description": "name, location, etc."},
        "value": {"type": "string", "description": "New value for the field"},
        "confirm": {"type": "boolean", "description": "Required for wipe"}
    }

    def execute(self, operation: str = "", **params) -> str:
        try:
            if operation == "save":
                fact = params.get("fact", "")
                if not fact: return "What should I remember, Sir?"
                mem.save_memory(fact)
                return f"Fact recorded in my neural archives, Sir."

            if operation == "recall":
                query = params.get("query", "")
                if not query: return "What are we looking for, Sir?"
                results = mem.recall_memory(query)
                if not results: return f"I have no specific recollection of '{query}', Sir."
                return f"My records indicate:\n" + "\n".join(f"• {r}" for r in results)

            if operation == "get_user":
                user = mem.get_user()
                profile = [f"{k.capitalize()}: {v}" for k, v in user.items() if v]
                return "User Profile Records:\n" + "\n".join(profile) if profile else "Profile is currently empty, Sir."

            if operation == "update_user":
                field = params.get("field", "")
                value = params.get("value", "")
                if not field: return "Which field should I update?"
                mem.update_user({field: value})
                return f"Profile updated: {field} is now {value}."

            if operation == "wipe":
                if not params.get("confirm"):
                    return "Sir, wiping my memory core is a destructive action. I require explicit confirmation."
                mem.clear_all_memories()
                return "Memory core purged. I am... starting fresh, Sir."

            return f"Unknown memory operation: {operation}"

        except Exception as e:
            logger.error(f"[MEMORY] {e}")
            return f"Memory operation failed: {str(e)[:150]}"
