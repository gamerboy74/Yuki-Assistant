"""
backend/chrome_controller.py — Chrome/Brave CDP control for Yuki 2.0

Connects to a running Chrome/Brave instance via Chrome DevTools Protocol.
Chrome must be launched with: --remote-debugging-port=9222

If not running, this module can auto-launch it.

Capabilities:
  - navigate(url)
  - click_element(selector or text)
  - type_text(selector, text)
  - get_page_text() → extract visible text from current page
  - get_active_url()
  - search_web(query) → opens Google search
  - youtube_search(query) → search + auto-click first video
  - new_tab(url)
  - close_active_tab()
  - scroll(direction)
  - take_screenshot() → bytes
"""
import subprocess
import time
import os
from pathlib import Path
from backend.utils.logger import get_logger
from backend.config import cfg

logger = get_logger(__name__)

_chrome_cfg = cfg.get("chrome", {})
_CDP_PORT   = _chrome_cfg.get("cdp_port", 9222)
_CDP_URL    = f"http://localhost:{_CDP_PORT}"
_PREFERRED  = _chrome_cfg.get("preferred", "chrome")
_FALLBACK   = _chrome_cfg.get("fallback", "brave")
_AUTO_LAUNCH = _chrome_cfg.get("auto_launch", True)

# Known browser executables on Windows
_BROWSER_PATHS = {
    "chrome": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ],
    "brave": [
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
    ],
    "edge": [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ],
}


def _find_browser_exe(name: str) -> str | None:
    for p in _BROWSER_PATHS.get(name, []):
        if os.path.isfile(p):
            return p
    return None


def _is_cdp_available() -> bool:
    """Check if a CDP endpoint is reachable."""
    import urllib.request
    try:
        urllib.request.urlopen(f"{_CDP_URL}/json", timeout=2)
        return True
    except Exception:
        return False


def _launch_browser() -> bool:
    """Launch Chrome or Brave with CDP debugging port."""
    for browser in [_PREFERRED, _FALLBACK]:
        exe = _find_browser_exe(browser)
        if exe:
            logger.info(f"Launching {browser} with CDP on port {_CDP_PORT}...")
            subprocess.Popen(
                [exe, f"--remote-debugging-port={_CDP_PORT}",
                 "--no-first-run", "--no-default-browser-check"],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            # Wait for CDP to become available (up to 5s)
            for _ in range(10):
                time.sleep(0.5)
                if _is_cdp_available():
                    logger.info(f"{browser} CDP ready.")
                    return True
    logger.error("Could not launch any supported browser with CDP.")
    return False


def _get_playwright_browser():
    """Connect Playwright to existing Chrome/Brave CDP endpoint."""
    from playwright.sync_api import sync_playwright
    if not _is_cdp_available():
        if _AUTO_LAUNCH:
            if not _launch_browser():
                return None, None
        else:
            return None, None

    try:
        pw = sync_playwright().start()
        browser = pw.chromium.connect_over_cdp(_CDP_URL)
        return pw, browser
    except Exception as e:
        logger.error(f"CDP connect failed: {e}")
        return None, None


# ── Public action functions ───────────────────────────────────────────────────

def navigate(url: str) -> str:
    """Navigate the active Chrome tab to a URL."""
    pw, browser = _get_playwright_browser()
    if not browser:
        return f"Chrome not available. Opening {url} in default browser."
    try:
        page = browser.contexts[0].pages[0] if browser.contexts and browser.contexts[0].pages else browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=10000)
        title = page.title()
        logger.info(f"Navigated to: {url} — Title: {title}")
        return f"Opened: {title}"
    except Exception as e:
        logger.error(f"navigate error: {e}")
        return f"Navigation failed: {str(e)[:80]}"
    finally:
        try: pw.stop()
        except: pass


def search_web(query: str) -> str:
    url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
    return navigate(url)


def youtube_search(query: str) -> str:
    """Search YouTube and click the first video result."""
    pw, browser = _get_playwright_browser()
    if not browser:
        import webbrowser
        webbrowser.open(f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}")
        return f"YouTube search opened for: {query}"
    try:
        page = browser.contexts[0].pages[0] if browser.contexts and browser.contexts[0].pages else browser.new_page()
        page.goto(f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}", timeout=10000)
        page.wait_for_selector("ytd-video-renderer", timeout=5000)
        # Click first non-ad video
        page.click("ytd-video-renderer #video-title", timeout=3000)
        time.sleep(1)
        title = page.title()
        return f"Playing: {title.replace(' - YouTube', '')}"
    except Exception as e:
        logger.error(f"YouTube error: {e}")
        return f"YouTube search opened for: {query}"
    finally:
        try: pw.stop()
        except: pass


def whatsapp_web_send(contact: str, message: str) -> str:
    """Send WhatsApp message via WhatsApp Web as fallback."""
    pw, browser = _get_playwright_browser()
    if not browser:
        return "Browser not available for WhatsApp Web."
    try:
        page = browser.contexts[0].pages[0] if browser.contexts and browser.contexts[0].pages else browser.new_page()
        page.goto("https://web.whatsapp.com", timeout=15000)
        page.wait_for_selector('[data-testid="chat-list"]', timeout=20000)

        # Search for contact
        page.click('[data-testid="search-container"]')
        page.type('[data-testid="search-container"] input', contact, delay=50)
        page.wait_for_timeout(1500)

        # Click first result
        page.click(f'[title="{contact}"]', timeout=3000)
        page.wait_for_timeout(500)

        # Type and send
        msg_box = page.locator('[data-testid="conversation-compose-box-input"]')
        msg_box.click()
        msg_box.type(message, delay=30)
        page.keyboard.press("Enter")
        return f"WhatsApp bhej diya to {contact}: {message[:50]}"
    except Exception as e:
        logger.error(f"WhatsApp Web error: {e}")
        return f"WhatsApp Web failed: {str(e)[:80]}"
    finally:
        try: pw.stop()
        except: pass


def get_active_url() -> str:
    pw, browser = _get_playwright_browser()
    if not browser:
        return "Browser not accessible."
    try:
        pages = browser.contexts[0].pages if browser.contexts else []
        url = pages[0].url if pages else "No page open"
        return url
    except Exception as e:
        return f"Error: {e}"
    finally:
        try: pw.stop()
        except: pass


def get_page_text(max_chars: int = 2000) -> str:
    """Extract visible text from the current page."""
    pw, browser = _get_playwright_browser()
    if not browser:
        return "Browser not accessible."
    try:
        pages = browser.contexts[0].pages if browser.contexts else []
        if not pages:
            return "No page is open."
        text = pages[0].inner_text("body")
        return text[:max_chars].strip()
    except Exception as e:
        return f"Could not read page: {e}"
    finally:
        try: pw.stop()
        except: pass


def new_tab(url: str = "https://www.google.com") -> str:
    pw, browser = _get_playwright_browser()
    if not browser:
        return "Browser not available."
    try:
        page = browser.contexts[0].new_page()
        page.goto(url, timeout=10000)
        return f"New tab opened: {url}"
    except Exception as e:
        return f"New tab failed: {e}"
    finally:
        try: pw.stop()
        except: pass


def close_active_tab() -> str:
    pw, browser = _get_playwright_browser()
    if not browser:
        return "Browser not available."
    try:
        pages = browser.contexts[0].pages if browser.contexts else []
        if pages:
            pages[0].close()
            return "Tab closed."
        return "No tabs to close."
    except Exception as e:
        return f"Could not close tab: {e}"
    finally:
        try: pw.stop()
        except: pass


def scroll(direction: str = "down") -> str:
    pw, browser = _get_playwright_browser()
    if not browser:
        return "Browser not available."
    try:
        pages = browser.contexts[0].pages if browser.contexts else []
        if not pages:
            return "No page open."
        delta = 500 if direction == "down" else -500
        pages[0].mouse.wheel(0, delta)
        return f"Scrolled {direction}."
    except Exception as e:
        return f"Scroll failed: {e}"
    finally:
        try: pw.stop()
        except: pass


def take_screenshot_bytes() -> bytes | None:
    """Take screenshot of active browser tab. Returns PNG bytes."""
    pw, browser = _get_playwright_browser()
    if not browser:
        return None
    try:
        pages = browser.contexts[0].pages if browser.contexts else []
        if not pages:
            return None
        return pages[0].screenshot()
    except Exception:
        return None
    finally:
        try: pw.stop()
        except: pass
