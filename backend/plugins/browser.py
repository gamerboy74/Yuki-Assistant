import os
import time
import subprocess
from pathlib import Path
from typing import Optional
from backend.plugins._base import Plugin
from backend.utils.logger import get_logger
from backend.config import cfg

logger = get_logger(__name__)

# ── Persistent Browser State ──
_pw = None
_browser = None

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
        self.preferred = cfg.get("chrome", {}).get("preferred", "chrome").lower()

    def _find_browser_executable(self) -> Optional[str]:
        """Discovery logic for browser binaries on Windows."""
        if self.preferred == "brave":
            paths = [
                os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
                r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
                r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe"
            ]
        else: # Default/Chrome
            paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
            ]
            
        for p in paths:
            if os.path.exists(p): return p
        return None

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
        """
        Persistent CDP connection.
        FALLBACK Logic:
        If user's Chrome/Brave is not running on 9222, we attempt Auto-Launch.
        We poll for the connection instead of a single wait to prevent race conditions.
        """
        global _pw, _browser
        from playwright.sync_api import sync_playwright

        try:
            if _pw is None:
                _pw = sync_playwright().start()

            if _browser is None or not _browser.is_connected():
                # Step 1: Attempt quick link to existing instance
                try:
                    logger.info(f"[BROWSER] Linking to CDP at {self.cdp_url}...")
                    _browser = _pw.chromium.connect_over_cdp(self.cdp_url, timeout=1500)
                except Exception:
                    # Step 2: Auto-Launch if enabled
                    auto_launch = cfg.get("chrome", {}).get("auto_launch", True)
                    if auto_launch:
                        exe = self._find_browser_executable()
                        if exe:
                            logger.info(f"[BROWSER] Auto-Launch: Spawning {self.preferred} with debugging...")
                            subprocess.Popen(f'start "" "{exe}" --remote-debugging-port={self.cdp_port}', shell=True)
                            
                            # Polling loop: 15 seconds to allow browser to initialize
                            for i in range(15):
                                time.sleep(1)
                                try:
                                    logger.info(f"[BROWSER] Connection attempt {i+1}/15...")
                                    _browser = _pw.chromium.connect_over_cdp(self.cdp_url, timeout=2000)
                                    if _browser.is_connected():
                                        logger.info(f"[BROWSER] Successfully linked on attempt {i+1}.")
                                        break
                                except:
                                    continue
                    
                    # Step 3: Final fallback check
                    if _browser is None or not _browser.is_connected():
                        if auto_launch:
                            # IMPORTANT: Don't go headless if the user expected a visible launch
                            logger.error("[BROWSER] Hardware link failed. Aborting to avoid UI desync.")
                            raise Exception(f"Started {self.preferred}, but the control link timed out. Sir, is the browser already open in another window?")
                        
                        logger.warning(f"[BROWSER] Fallback: Spawning autonomous headless instance...")
                        _browser = _pw.chromium.launch(headless=True)
            
            context = _browser.contexts[0] if _browser.contexts else _browser.new_context()
            page = context.pages[0] if context.pages else context.new_page()
            return page
        except Exception as e:
            logger.error(f"[BROWSER] Critical failure in browser link: {e}")
            if _pw: 
                try: _pw.stop()
                except: pass
                _pw = None
            _browser = None
            raise e

    def _cleanup(self) -> str:
        """Browser Hygiene: Close stale contexts and pages to free up RAM."""
        global _browser
        if not _browser or not _browser.is_connected():
            return "Browser not active."
        
        try:
            # Keep only the active context and page
            for context in _browser.contexts[1:]:
                context.close()
            
            if _browser.contexts:
                ctx = _browser.contexts[0]
                for page in ctx.pages[1:]:
                    page.close()
            
            return "Browser memory flushed. Stale contexts released."
        except Exception as e:
            return f"Hygiene failed: {e}"

    def _get_fresh_page(self):
        """Get or create a live page. If the current page is closed, opens a new one."""
        global _browser
        context = _browser.contexts[0] if _browser.contexts else _browser.new_context()
        # Try existing page first; if it's closed/dead, open a new one
        for page in context.pages:
            try:
                _ = page.url  # Will raise if page is closed
                return page
            except Exception:
                continue
        return context.new_page()

    def _navigate(self, url: str) -> str:
        if not url: return "No URL provided."
        if not url.startswith(("http", "www.")): url = "https://" + url
        
        try:
            page = self._get_page()
            page.goto(url, wait_until="load", timeout=25000)
            title = page.title()
            return f"Navigated to '{title}'."
        except Exception as e:
            err = str(e)
            if "Target page, context or browser has been closed" in err or "Target closed" in err:
                logger.warning("[BROWSER] Page was closed — opening fresh page and retrying.")
                try:
                    page = self._get_fresh_page()
                    page.goto(url, wait_until="load", timeout=25000)
                    title = page.title()
                    return f"Navigated to '{title}'."
                except Exception as e2:
                    raise e2
            raise e

    def _search(self, query: str) -> str:
        if not query: return "Search query is empty."
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        return self._navigate(url)

    def _read(self) -> str:
        try:
            page = self._get_page()
            _ = page.url  # Probe liveness
        except Exception:
            logger.warning("[BROWSER] Active page was closed — using fresh page.")
            page = self._get_fresh_page()

        text = page.evaluate("""() => {
            const selectors = ['article', 'main', '[role=main]', '.content', '#content', '.post-content'];
            for (const sel of selectors) {
                const el = document.querySelector(sel);
                if (el && el.innerText.length > 200) return el.innerText;
            }
            return document.body.innerText;
        }""").strip()
        
        return text[:3000] # Safe limit for high-quality content


    def _click(self, target: str) -> str:
        if not target: return "No target to click."
        page = self._get_page()
        try:
            page.get_by_text(target, exact=False).first.click(timeout=5000)
            return f"Clicked '{target}'."
        except:
            page.click(target, timeout=3000)
            return f"Clicked selector '{target}'."

    def _scroll(self, direction: str) -> str:
        page = self._get_page()
        delta = 600 if direction == "down" else -600
        page.mouse.wheel(0, delta)
        return f"Scrolled {direction}."

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

class SearchInChromePlugin(BrowserPlugin):
    name = "search_in_chrome"
    description = "Perform a search directly in the Chrome browser."
    parameters = {"query": {"type": "string", "description": "Search query", "required": True}}
    def execute(self, query: str = "", **_) -> str:
        return self._search(query)

class BrowserHygienePlugin(BrowserPlugin):
    name = "browser_hygiene"
    description = "Clean up browser memory and close stale tabs to reduce RAM usage."
    parameters = {}
    def execute(self, **_) -> str:
        return self._cleanup()
