"""
rss.py — RSS/Atom Feed Plugin
Provides the agent with the ability to read and summarize news feeds.
"""

import feedparser
from typing import List, Dict, Optional
from backend.plugins._base import Plugin
from backend.utils.logger import get_logger
from backend.config import cfg

logger = get_logger(__name__)

class RSSPlugin(Plugin):
    name = "read_rss_feed"
    description = "Read news or updates from an RSS/Atom feed URL."
    parameters = {
        "url": {
            "type": "string", 
            "description": "The URL of the RSS/Atom feed to read.", 
            "required": True
        },
        "limit": {
            "type": "integer", 
            "description": "Maximum number of entries to retrieve (default: 5).", 
            "required": False
        }
    }

    def execute(self, url: str = "", limit: int = 5, **_) -> str:
        if not url:
            return "Error: No RSS URL provided."
        
        # Check if the URL is a "favorite" name (e.g. "TechCrunch")
        favorites = cfg.get("rss", {}).get("favorite_feeds", [])
        for fav in favorites:
            if url.lower() == fav.get("name", "").lower():
                url = fav.get("url")
                break

        logger.info(f"[RSS] Fetching feed: {url}")
        
        try:
            feed = feedparser.parse(url)
            
            if feed.bozo:
                # Bozo=1 means there's a malformed feed, but it might still have entries
                logger.warning(f"[RSS] Feed report 'bozo' flag (malformed): {url}")
            
            if not feed.entries:
                return f"I couldn't find any entries in the RSS feed at {url}. It might be empty or restricted."

            output = [f"### Latest from: {feed.feed.get('title', url)}"]
            
            # Limit entries
            entries = feed.entries[:limit]
            
            for i, entry in enumerate(entries, 1):
                title = entry.get("title", "No Title")
                link = entry.get("link", "")
                summary = entry.get("summary", "")
                # Clean up summary (remove HTML tags if any)
                import re
                summary = re.sub('<[^<]+?>', '', summary)[:200]
                
                output.append(f"{i}. **{title}**")
                output.append(f"   - {summary}...")
                if link:
                    output.append(f"   - [Read more]({link})")
                output.append("")

            return "\n".join(output)

        except Exception as e:
            logger.error(f"[RSS] Failed to fetch feed {url}: {e}")
            return f"Error fetching RSS feed: {str(e)}"
