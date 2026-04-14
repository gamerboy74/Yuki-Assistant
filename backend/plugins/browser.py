"""
browser.py — Modular Browser Control
Dynamic, reactive configuration for high-performance agentic research.

FIXES APPLIED:
  [1] Port-binding check before spawn — prevents single-instance Brave ghost problem
  [2] Popen handle stored — zombie process leak eliminated
  [3] Session-level circuit breaker — stops orchestrator retry storms
  [4] _get_page() decomposed — init / connect / launch / recover are separate concerns
  [5] os.access(X_OK) removed — it's a no-op on Windows, replaced with try/except
  [6] SearchInChromePlugin removed — was an exact duplicate of SearchWebPlugin
  [7] Hygiene guard added — won't run cleanup on a browser that never connected
"""

import os
import time
import socket
import subprocess
from typing import Optional
from backend.plugins._base import Plugin
from backend.utils.logger import get_logger
from backend.config import cfg

logger = get_logger(__name__)

# ── Persistent Browser State ──────────────────────────────────────────────────
_pw           = None
_browser      = None
_browser_proc: Optional[subprocess.Popen] = None   # FIX [2]: track spawned process
_failure_count = 0                                  # FIX [3]: circuit breaker counter
_CIRCUIT_LIMIT = 1                                  # trips after N consecutive failures


# ── Internal Helpers (module-level, not class methods) ────────────────────────

def _is_port_bound(port: int) -> bool:
    """FIX [1]: Check if CDP port is already answering before we try to spawn."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("localhost", port)) == 0


def _kill_browser_proc():
    """FIX [2]: Terminate the spawned browser process if we have a handle."""
    global _browser_proc
    if _browser_proc is not None:
        try:
            _browser_proc.terminate()
            _browser_proc.wait(timeout=3)
            logger.info("[BROWSER] Spawned browser process terminated.")
        except Exception as e:
            logger.warning(f"[BROWSER] Could not terminate browser proc: {e}")
        _browser_proc = None


def _trip_circuit():
    """FIX [3]: Increment failure counter. Raise immediately if limit reached."""
    global _failure_count
    _failure_count += 1
    if _failure_count >= _CIRCUIT_LIMIT:
        logger.error(
            f"[BROWSER] Circuit breaker tripped after {_failure_count} failures. "
            "Blocking further browser attempts this session."
        )
        raise RuntimeError(
            "Browser circuit breaker open. The browser failed to connect "
            f"{_failure_count} times this session. Restart the assistant or "
            "manually open Brave with --remote-debugging-port=9222 before trying again."
        )


def _reset_circuit():
    """Called on successful connection."""
    global _failure_count
    _failure_count = 0


# ── Core Browser Class ────────────────────────────────────────────────────────

class BrowserPlugin(Plugin):
    """Base class for browser operations. All browser tools inherit from this."""
    description = "Base class for browser tools."

    # ── Config Properties ──────────────────────────────────────────────────

    @property
    def chrome_cfg(self):
        return cfg.get("chrome", {})

    @property
    def preferred(self):
        return self.chrome_cfg.get("preferred", "brave").lower()

    @property
    def cdp_port(self):
        return self.chrome_cfg.get("cdp_port", 9222)

    @property
    def cdp_url(self):
        return f"http://localhost:{self.cdp_port}"

    # ── Browser Discovery ──────────────────────────────────────────────────

    def _find_browser_executable(self) -> Optional[str]:
        """Locate browser binary on Windows. Returns path or None."""
        pref = self.preferred
        if pref == "brave":
            candidates = [
                os.path.expandvars(
                    r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"
                ),
                r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
                r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
            ]
        else:
            candidates = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                os.path.expandvars(
                    r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
                ),
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            ]

        for p in candidates:
            if os.path.exists(p):
                return p
        return None

    # ── FIX [4]: Decomposed connection logic ───────────────────────────────

    def _init_playwright(self):
        """Step 1: Start the Playwright runtime if not already running."""
        global _pw
        if _pw is None:
            from playwright.sync_api import sync_playwright
            _pw = sync_playwright().start()
            logger.info("[BROWSER] Playwright runtime started.")

    def _connect_existing(self) -> bool:
        """Step 2: Try to attach to an already-running browser on CDP port."""
        global _browser
        if not _is_port_bound(self.cdp_port):
            logger.info(f"[BROWSER] Port {self.cdp_port} not bound — no existing instance.")
            return False
        try:
            logger.info(f"[BROWSER] Port {self.cdp_port} is bound. Connecting...")
            _browser = _pw.chromium.connect_over_cdp(self.cdp_url, timeout=2000)
            if _browser.is_connected():
                logger.info("[BROWSER] Attached to existing browser instance.")
                return True
        except Exception as e:
            logger.warning(f"[BROWSER] Port was bound but connect failed: {e}")
        return False

    def _spawn_and_connect(self) -> bool:
        """
        Step 3: Auto-launch browser with debug port and poll for connection.
        
        FIX [1]: We only spawn if the port is NOT already bound.
                 Brave's single-instance behavior means spawning while another
                 instance is open (without --remote-debugging-port) causes the
                 new process to hand off and exit silently — leaving us polling
                 a port that will never open.
        FIX [2]: Store the Popen handle so we can kill it on failure.
        FIX [5]: os.access(X_OK) removed — always True on Windows, useless.
                 We let Popen raise if the binary is bad.
        """
        global _browser, _browser_proc

        if not self.chrome_cfg.get("auto_launch", True):
            return False

        exe = self._find_browser_executable()
        if not exe:
            logger.error("[BROWSER] No browser binary found. Cannot auto-launch.")
            return False

        # FIX [1]: If port is already bound to something that rejected us, kill
        # whatever's there rather than spawning on top of it. We can't do that
        # without admin rights reliably, so instead we bail with a clear message.
        if _is_port_bound(self.cdp_port):
            logger.error(
                f"[BROWSER] Port {self.cdp_port} is bound but not accepting CDP. "
                "Something else owns this port. Kill it or change cdp_port in config."
            )
            return False

        logger.info(f"[BROWSER] Spawning {self.preferred} with --remote-debugging-port={self.cdp_port}...")

        try:
            # FIX [2, 8]: Store handle and use isolated profile
            # Isolated profile prevents locking conflicts with the user's main browser.
            import tempfile
            user_data_dir = os.path.join(tempfile.gettempdir(), "yuki_cdp_profile")
            
            _browser_proc = subprocess.Popen(
                [
                    exe, 
                    f"--remote-debugging-port={self.cdp_port}", 
                    f"--user-data-dir={user_data_dir}",
                    "--no-first-run", 
                    "--no-default-browser-check"
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            # FIX [5]: Catch actual spawn errors instead of relying on os.access
            logger.error(f"[BROWSER] Failed to spawn browser: {e}")
            return False

        max_attempts = 20
        for i in range(max_attempts):
            time.sleep(1)
            logger.info(f"[BROWSER] Connection attempt {i+1}/{max_attempts}...")
            if not _is_port_bound(self.cdp_port):
                # Port not open yet — keep waiting
                continue
            try:
                _browser = _pw.chromium.connect_over_cdp(self.cdp_url, timeout=2000)
                if _browser.is_connected():
                    logger.info(f"[BROWSER] Successfully connected on attempt {i+1}.")
                    return True
            except Exception:
                continue

        # Spawn failed — clean up the zombie
        logger.error("[BROWSER] Spawn succeeded but CDP never became available.")
        _kill_browser_proc()  # FIX [2]
        return False

    def _get_page(self):
        """
        Main entry point. Returns a live page, or raises with a clear error.
        Circuit breaker prevents orchestrator retry storms. FIX [3].
        """
        global _pw, _browser, _failure_count

        # FIX [3]: Hard stop if we've already failed too many times
        if _failure_count >= _CIRCUIT_LIMIT:
            raise RuntimeError(
                "Browser circuit breaker open. The browser failed to connect "
                f"{_failure_count} times this session. "
                "Restart the assistant or open Brave with --remote-debugging-port=9222."
            )

        try:
            self._init_playwright()

            # Re-use existing connection if still alive
            if _browser is not None and _browser.is_connected():
                pass  # fall through to page acquisition
            else:
                _browser = None
                if not self._connect_existing():
                    if not self._spawn_and_connect():
                        _trip_circuit()  # FIX [3]
                        raise RuntimeError(
                            f"Could not connect to or launch {self.preferred}. "
                            "Is it already open without the debug flag?"
                        )

            _reset_circuit()  # FIX [3]: success resets the counter

            context = _browser.contexts[0] if _browser.contexts else _browser.new_context()
            page = context.pages[0] if context.pages else context.new_page()
            return page

        except RuntimeError:
            raise  # circuit breaker errors pass through unchanged
        except Exception as e:
            logger.error(f"[BROWSER] Critical failure: {e}")
            # Teardown cleanly
            if _pw:
                try:
                    _pw.stop()
                except Exception:
                    pass
                _pw = None
            _browser = None
            _kill_browser_proc()  # FIX [2]
            _trip_circuit()       # FIX [3]
            raise

    def _get_fresh_page(self):
        """Get a live page. Opens a new tab if all existing pages are dead."""
        global _browser
        context = _browser.contexts[0] if _browser.contexts else _browser.new_context()
        for page in context.pages:
            try:
                _ = page.url  # Probe liveness
                return page
            except Exception:
                continue
        return context.new_page()

    # ── Browser Actions ────────────────────────────────────────────────────

    def _navigate(self, url: str) -> str:
        if not url:
            return "No URL provided."
        if not url.startswith(("http://", "https://", "www.")):
            url = "https://" + url

        try:
            page = self._get_page()
            page.goto(url, wait_until="load", timeout=25000)
            return f"Navigated to '{page.title()}'."
        except Exception as e:
            err = str(e).lower()
            if "closed" in err or "target" in err:
                logger.warning("[BROWSER] Page was closed — retrying with fresh page.")
                try:
                    page = self._get_fresh_page()
                    page.goto(url, wait_until="load", timeout=25000)
                    return f"Navigated to '{page.title()}' (retry successful)."
                except Exception as e2:
                    raise e2
            raise

    def _search(self, query: str) -> str:
        if not query:
            return "Search query is empty."
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        return self._navigate(url)

    def _read(self) -> str:
        try:
            page = self._get_page()
            _ = page.url  # Probe liveness
        except Exception:
            logger.warning("[BROWSER] Active page dead — using fresh page.")
            page = self._get_fresh_page()

        text = page.evaluate("""() => {
            const selectors = [
                'article', 'main', '[role=main]',
                '.content', '#content', '.post-content'
            ];
            for (const sel of selectors) {
                const el = document.querySelector(sel);
                if (el && el.innerText.length > 200) return el.innerText;
            }
            return document.body.innerText;
        }""").strip()

        return text[:3000]

    def _click(self, target: str) -> str:
        if not target:
            return "No target specified."
        page = self._get_page()
        try:
            page.get_by_text(target, exact=False).first.click(timeout=5000)
            return f"Clicked '{target}'."
        except Exception:
            page.click(target, timeout=3000)
            return f"Clicked selector '{target}'."

    def _scroll(self, direction: str) -> str:
        page = self._get_page()
        delta = 600 if direction == "down" else -600
        page.mouse.wheel(0, delta)
        return f"Scrolled {direction}."

    def _cleanup(self) -> str:
        """
        FIX [7]: Guard against running hygiene when browser never connected.
        Close stale contexts and tabs. Keep context[0] and page[0].
        """
        global _browser
        if not _browser or not _browser.is_connected():
            return "Browser not active — nothing to clean."

        try:
            for context in _browser.contexts[1:]:
                context.close()
            if _browser.contexts:
                ctx = _browser.contexts[0]
                for page in ctx.pages[1:]:
                    page.close()
            return "Browser memory flushed. Stale contexts released."
        except Exception as e:
            return f"Hygiene failed: {e}"


# ── Concrete Plugin Classes ───────────────────────────────────────────────────

class SearchWebPlugin(BrowserPlugin):
    name        = "search_internet"
    description = "Search the web for information using the browser."
    parameters  = {
        "query": {"type": "string", "description": "Search term", "required": True}
    }

    def execute(self, query: str = "", **_) -> str:
        return self._search(query)


class ReadPagePlugin(BrowserPlugin):
    name        = "read_active_tab"
    description = "Extract text content from the currently active browser tab."
    parameters  = {}

    def execute(self, **_) -> str:
        return self._read()


class BrowserNavigatePlugin(BrowserPlugin):
    name        = "browser_navigate"
    description = "Open a specific URL in the browser."
    parameters  = {
        "url": {"type": "string", "description": "URL to visit", "required": True}
    }

    def execute(self, url: str = "", **_) -> str:
        return self._navigate(url)


class BrowserHygienePlugin(BrowserPlugin):
    name        = "browser_hygiene"
    description = "Close stale browser tabs and free RAM. Only useful after active browsing sessions."
    parameters  = {}

    def execute(self, **_) -> str:
        return self._cleanup()


# FIX [6]: SearchInChromePlugin was a 1:1 duplicate of SearchWebPlugin.
# DELETED. If your orchestrator config still references 'search_in_chrome',
# remap it to 'search_internet'.