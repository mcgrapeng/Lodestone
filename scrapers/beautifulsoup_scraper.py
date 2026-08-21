# -*- coding: utf-8 -*-
"""BeautifulSoup4 adapter — robust HTML parsing for when regex fails.

Use case: GitHub Trending sometimes returns odd markup (e.g. spans nested
in spans, broken attributes). Regex from fetch_github_trending can miss
repos. BeautifulSoup parses the DOM properly and re-serializes it, which
makes the regex parser work on cleaner HTML.

GitHub: https://www.crummy.com/software/BeautifulSoup/
Install: pip install beautifulsoup4
"""

import asyncio


def is_available() -> bool:
    try:
        import bs4  # noqa: F401

        return True
    except ImportError:
        return False


async def _async_scrape(url: str, timeout: int = 30) -> dict:
    """Fetch via urllib then parse+reserialize through BeautifulSoup. The
    'html' field is the cleaned HTML — drop-in replacement for the raw
    GitHub Trending HTML.
    """
    try:
        import urllib.request

        def _do():
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0 (lodestone/bs4)"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            try:
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(raw, "html.parser")
                cleaned = str(soup)
            except Exception:
                cleaned = raw
            return {"success": bool(cleaned), "html": cleaned, "error": None}

        return await asyncio.to_thread(_do)
    except Exception as e:
        return {
            "success": False,
            "html": "",
            "error": f"beautifulsoup: {type(e).__name__}: {e}",
        }


def scrape(url: str, timeout: int = 30) -> dict:
    """Sync entry — wraps the async core via asyncio.run."""
    try:
        return asyncio.run(_async_scrape(url, timeout))
    except Exception as e:
        return {
            "success": False,
            "html": "",
            "error": f"beautifulsoup: {type(e).__name__}: {e}",
        }
