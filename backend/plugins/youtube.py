"""YouTube plugin — search and play videos."""

import webbrowser
from backend.plugins._base import Plugin


class YouTubePlugin(Plugin):
    name = "play_youtube"
    description = "Search and play YouTube video."
    parameters = {
        "query": {
            "type": "string",
            "description": "Video or topic to search for",
            "required": True,
        },
    }

    def execute(self, query: str = "", **_) -> str:
        if not query:
            webbrowser.open("https://www.youtube.com")
            return "Opened YouTube."
            
        import urllib.request
        import urllib.parse
        import re
        
        try:
            # Fetch youtube search HTML
            encoded = urllib.parse.quote(query)
            url = f"https://www.youtube.com/results?search_query={encoded}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            html = urllib.request.urlopen(req, timeout=5).read().decode('utf-8')
            
            # Find the first video ID
            video_ids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)
            if video_ids:
                # Remove duplicates while preserving order
                unique_ids = list(dict.fromkeys(video_ids))
                # Append &list=RD{video_id} to trigger a YouTube Mix (Radio)
                # This ensures "Next" and "Prev" media buttons work in the browser.
                video_url = f"https://www.youtube.com/watch?v={unique_ids[0]}&list=RD{unique_ids[0]}"
                webbrowser.open(video_url)
                return f"Playing '{query}' on YouTube."
            else:
                # Fallback to search results
                webbrowser.open(url)
                return f"Could not auto-play. Showing search results for '{query}'."
        except Exception as e:
            # Fallback on network/parse error
            webbrowser.open(f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}")
            return f"Playing '{query}' on YouTube."
