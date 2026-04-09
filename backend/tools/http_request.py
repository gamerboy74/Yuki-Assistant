"""
HTTP request tool — lets the LLM fetch web data.

Used for: weather, APIs, quick web lookups.
"""

from backend.utils.logger import get_logger

logger = get_logger(__name__)


def http_get(url: str, timeout: int = 8) -> str:
    """
    Fetch a URL and return the text response, truncated to 2000 chars.
    Only allows http/https protocols.
    """
    if not url.startswith(("http://", "https://")):
        return "Only http:// and https:// URLs are allowed."

    try:
        import requests
        resp = requests.get(
            url,
            headers={"User-Agent": "Yuki-Assistant/4.0"},
            timeout=timeout,
        )
        resp.raise_for_status()
        text = resp.text.strip()

        if len(text) > 2000:
            text = text[:2000] + "\n... (truncated)"

        logger.info(f"[HTTP] GET {url} → {len(text)} chars")
        return text or "(empty response)"

    except Exception as e:
        logger.error(f"[HTTP] GET {url} failed: {e}")
        return f"HTTP request failed: {str(e)[:150]}"
