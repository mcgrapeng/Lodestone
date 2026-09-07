# -*- coding: utf-8 -*-
"""requests-html adapter — JS-rendered HTTP without a browser binary.

Use case: lightweight JS rendering (uses pyppeteer under the hood only when
.render() is called). For lodestone we use the simple .html property which is
plain requests — fast, no Chrome download required.

GitHub: https://github.com/kennethreitz/requests-html
Install: pip install requests-html
"""

import asyncio

from .config_loader import get_timeout, get_user_agent


def is_available() -> bool:
    try:
        import requests_html  # noqa: F401  # type: ignore[import-not-found]

        return True
    except ImportError:
        return False


async def _async_scrape(url: str, timeout: int = 60) -> dict:
    """Fetch raw HTML via requests-html's session (requests under the hood).
    timeout = seconds (0 → load from config.toml [timeouts].requests_html).
    """
    if not timeout:
        timeout = get_timeout("requests_html", 45)
    ua = get_user_agent("requests_html", "Mozilla/5.0 (lodestone/requests-html)")

    def _do():
        from requests_html import HTMLSession  # type: ignore[import-not-found]

        s = HTMLSession()
        try:
            r = s.get(url, timeout=timeout, headers={"User-Agent": ua})
            if r.status_code == 200 and r.text:
                return {"success": True, "html": r.text, "error": None}
            return {
                "success": False,
                "html": "",
                "error": f"requests_html: HTTP {r.status_code}",
            }
        finally:
            s.close()

    try:
        return await asyncio.to_thread(_do)
    except Exception as e:
        return {
            "success": False,
            "html": "",
            "error": f"requests_html: {type(e).__name__}: {e}",
        }


def scrape(url: str, timeout: int = 60) -> dict:
    """Sync entry — wraps the async core via asyncio.run. Pass 0 to use config default."""
    if not timeout:
        timeout = get_timeout("requests_html", 45)
    try:
        return asyncio.run(_async_scrape(url, timeout))
    except Exception as e:
        return {
            "success": False,
            "html": "",
            "error": f"requests_html: {type(e).__name__}: {e}",
        }