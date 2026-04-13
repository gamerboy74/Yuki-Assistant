"""Spotify plugin — search and play music via Spotify desktop app."""

import os
import re
import subprocess
import threading
import time
from backend.plugins._base import Plugin
from backend import memory as mem
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class SpotifyPlugin(Plugin):
    name = "play_spotify"
    description = "Search and play a song, artist, or playlist on the Spotify desktop app."
    parameters = {
        "query": {
            "type": "string",
            "description": "Song name, artist, or playlist to play",
            "required": True,
        },
    }

    def execute(self, query: str = "", **_) -> str:
        if not query:
            try:
                os.startfile("spotify:")
            except Exception:
                pass
            return "Opened Spotify."

        import urllib.parse
        encoded = urllib.parse.quote(query)
        track_uri = None

        # Strategy A: scrape DuckDuckGo for a direct track URI
        try:
            import urllib.request
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query + ' spotify song')}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            html = urllib.request.urlopen(req, timeout=5).read().decode("utf-8")
            m = re.search(r"open\.spotify\.com/track/([a-zA-Z0-9]{22})", html)
            if m:
                track_uri = f"spotify:track:{m.group(1)}"
        except Exception as e:
            logger.debug(f"Spotify scrape failed: {e}")

        try:
            if track_uri:
                os.startfile(track_uri)
                self._auto_play_track()
                mem.set("last_played_track", query)
                return f"Playing {query} on Spotify."
            else:
                os.startfile(f"spotify:search:{encoded}")
                self._auto_play_search()
                mem.set("last_played_track", query)
                return f"Searching Spotify for {query} and attempting auto-play."
        except Exception as e:
            logger.error(f"Spotify startfile error: {e}")
            return f"Couldn't open Spotify: {str(e)[:100]}"

    @staticmethod
    def _auto_play_track():
        def _run():
            time.sleep(3.0)
            script = (
                "$wshell = New-Object -ComObject wscript.shell; "
                "$proc = Get-Process -Name 'Spotify' -ErrorAction SilentlyContinue | "
                "Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1; "
                "if ($proc) { $wshell.AppActivate($proc.Id); Start-Sleep -m 500; "
                "$wshell.SendKeys('{ENTER}'); }"
            )
            subprocess.Popen(
                ["powershell", "-WindowStyle", "Hidden", "-Command", script],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        threading.Thread(target=_run, daemon=True).start()

    @staticmethod
    def _auto_play_search():
        def _run():
            time.sleep(3.5)
            script = (
                "$wshell = New-Object -ComObject wscript.shell; "
                "$proc = Get-Process -Name 'Spotify' -ErrorAction SilentlyContinue | "
                "Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1; "
                "if ($proc) { $wshell.AppActivate($proc.Id); Start-Sleep -m 500; "
                "$wshell.SendKeys('{TAB}'); Start-Sleep -m 100; "
                "$wshell.SendKeys('{TAB}'); Start-Sleep -m 100; "
                "$wshell.SendKeys('{ENTER}'); }"
            )
            subprocess.Popen(
                ["powershell", "-WindowStyle", "Hidden", "-Command", script],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        threading.Thread(target=_run, daemon=True).start()