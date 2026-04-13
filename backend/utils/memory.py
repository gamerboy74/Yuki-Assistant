import sqlite3
import os
from datetime import datetime
from backend.utils.logger import get_logger

logger = get_logger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "yuki_memory.db")

class MemoryManager:
    """Manages long-term semantic knowledge for Yuki."""
    def __init__(self):
        self._init_db()

    def _init_db(self):
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS knowledge (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    category TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to initialize memory DB: {e}")

    def add_fact(self, content: str, category: str = "general"):
        """Store a new piece of knowledge."""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO knowledge (content, category) VALUES (?, ?)", (content, category))
            conn.commit()
            conn.close()
            logger.info(f"Yuki remembered: {content}")
        except Exception as e:
            logger.error(f"Failed to save fact: {e}")

    def get_recent_facts(self, limit: int = 5) -> str:
        """Retrieve recent context to inject into current turn."""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT content FROM knowledge ORDER BY created_at DESC LIMIT ?", (limit,))
            facts = [row[0] for row in cursor.fetchall()]
            conn.close()
            if not facts:
                return ""
            return "\n".join([f"- {f}" for f in facts])
        except Exception as e:
            logger.error(f"Failed to retrieve facts: {e}")
            return ""

# Singleton
memory = MemoryManager()
