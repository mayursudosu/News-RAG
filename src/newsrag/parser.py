"""Article text extraction from URLs.

Uses trafilatura (fast, accurate) with BeautifulSoup as fallback.
"""

from __future__ import annotations

import requests
from bs4 import BeautifulSoup

try:
    import trafilatura
    _HAS_TRAFILATURA = True
except ImportError:
    _HAS_TRAFILATURA = False

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}
_TIMEOUT = 15  # seconds


def extract_text(url: str) -> str:
    """Download *url* and return the main article text (plain text).

    Returns an empty string on failure rather than raising.
    """
    if not url:
        return ""

    # ── Strategy 1: trafilatura (best quality) ──────────────────────────
    if _HAS_TRAFILATURA:
        try:
            downloaded = trafilatura.fetch_url(url)
            if downloaded:
                text = trafilatura.extract(downloaded)
                if text and len(text) > 120:
                    return text.strip()
        except Exception:
            pass  # fall through to fallback

    # ── Strategy 2: requests + BeautifulSoup ────────────────────────────
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # Remove noisy elements
        for tag in soup(["script", "style", "nav", "header", "footer",
                         "aside", "figure", "figcaption", "iframe"]):
            tag.decompose()

        # Prefer <article> tag, else fall back to body
        article = soup.find("article") or soup.find("body")
        if article:
            text = article.get_text(separator="\n", strip=True)
            if len(text) > 120:
                return text
    except Exception:
        pass

    return ""
