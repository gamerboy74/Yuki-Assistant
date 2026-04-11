import os
import time
import subprocess
from pathlib import Path
from typing import Optional
from backend.plugins._base import Plugin
from backend.utils.logger import get_logger
from backend.config import cfg

logger = get_logger(__name__)

class BrowserPlugin(Plugin):
    name = "browser"
    description = "Control Chrome/Brave: navigate, search, read, click, scroll."
    parameters = {
        "operation": {
            "type": "string",
            "description": "Task: navigate, search, read, click, scroll",
            "enum": ["navigate", "search", "read", "click", "scroll"],
            "required": True
        },
        "url": {"type": "string", "description": "URL to visit", "required": False},
        "query": {"type": "string", "description": "Search query", "required": False},
        "target": {"type": "string", "description": "Element to click", "required": False},
        "direction": {"type": "string", "enum": ["up", "down"], "required": False}
    }

    def __init__(self):
        self.cdp_port = cfg.get("chrome", {}).get("cdp_port", 9222)
        self.cdp_url = f"http://localhost:{self.cdp_port}"

    def execute(self, operation: str = "", **params) -> str:
        try:
            if operation == "navigate":
                return self._navigate(params.get("url", ""))
            elif operation == "search":
                return self._search(params.get("query", ""))
            elif operation == "read":
                return self._read()
            elif operation == "click":
                return self._click(params.get("target", ""))
            elif operation == "scroll":
                return self._scroll(params.get("direction", "down"))
            return f"Unknown browser operation: {operation}"
        except Exception as e:
            logger.error(f"[BROWSER_PLUGIN] Error: {e}")
            return f"Browser error: {str(e)[:100]}"

    def _get_page(self):
        """Standard CDP connection logic."""
        from playwright.sync_api import sync_playwright
        # Note: In a production environment with many calls, we'd keep the browser open.
        # For now, we connect/disconnect to ensure state persists in the user's actual browser.
        pw = sync_playwright().start()
        try:
            browser = pw.chromium.connect_over_cdp(self.cdp_url)
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            page = context.pages[0] if context.pages else context.new_page()
            return pw, browser, page
        except Exception:
            # Fallback: Auto-launch or simple error
            pw.stop()
            raise Exception("Chrome CDP not available. Please launch Chrome with --remote-debugging-port=9222")

    def _navigate(self, url: str) -> str:
        if not url: return "No URL provided."
        if not url.startswith(("http", "www.")): url = "https://" + url
        
        pw, browser, page = self._get_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            title = page.title()
            return f"Navigated to '{title}'."
        finally:
            pw.stop()

    def _search(self, query: str) -> str:
        if not query: return "Search query is empty."
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        return self._navigate(url)

    def _read(self) -> str:
        pw, browser, page = self._get_page()
        try:
            # Aggressive noise filtering to save tokens
            text = page.evaluate("() => document.body.innerText").strip()
            return text[:4000] # Safe limit for LLM context
        finally:
            pw.stop()

    def _click(self, target: str) -> str:
        if not target: return "No target to click."
        pw, browser, page = self._get_page()
        try:
            page.get_by_text(target, exact=False).first.click(timeout=5000)
            return f"Clicked '{target}'."
        except:
            page.click(target, timeout=3000)
            return f"Clicked selector '{target}'."
        finally:
            pw.stop()

    def _scroll(self, direction: str) -> str:
        pw, browser, page = self._get_page()
        try:
            delta = 600 if direction == "down" else -600
            page.mouse.wheel(0, delta)
            return f"Scrolled {direction}."
        finally:
            pw.stop()

class SearchWebPlugin(BrowserPlugin):
    name = "search_internet" # Aliased to match Brain's expectation
    description = "Search the web."
    parameters = {"query": {"type": "string", "description": "Search term", "required": True}}
    def execute(self, query: str = "", **_) -> str:
        return self._search(query)

class ReadPagePlugin(BrowserPlugin):
    name = "read_active_tab"
    description = "Get text from current browser tab."
    parameters = {}
    def execute(self, **_) -> str:
        return self._read()

class BrowserNavigatePlugin(BrowserPlugin):
    name = "browser_navigate"
    description = "Open URL in browser."
    parameters = {"url": {"type": "string", "description": "URL", "required": True}}
    def execute(self, url: str = "", **_) -> str:
        return self._navigate(url)
