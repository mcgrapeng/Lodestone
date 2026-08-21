# -*- coding: utf-8 -*-
"""httpx adapter — modern async HTTP client (HTTP/2, connection pooling).

Use case: high-throughput fetches of public JSON APIs (HuggingFace, GitHub
core API, npm registry, PyPI JSON API). httpx is faster than urllib for
many sequential calls because of connection pooling + HTTP/2.

GitHub: https://github.com/encode/httpx
Install: pip install httpx
"""

import asyncio

from .config_loader import get_timeout, get_user_agent


def is_available() -> bool:
    try:
        import httpx  # noqa: F401

        return True
    except ImportError:
        return False


async def _async_scrape(url: str, timeout: int = 60) -> dict:
    """Async GET via httpx. timeout = seconds (0 → load from config.toml).
    Returns raw text as 'html' (httpx doesn't differentiate — caller decides how to parse).
    """
    if not timeout:
        timeout = get_timeout("httpx", 60)
    ua = get_user_agent("httpx", "Mozilla/5.0 (lodestone/httpx)")
    try:
        import httpx

        async with (
            httpx.AsyncClient(
                http2=False,  # requires h2 package; default off so it stays a zero-dep option
                follow_redirects=True,
                timeout=timeout,
                headers={"User-Agent": ua},
            ) as client
        ):
            r = await client.get(url)
            if r.status_code == 200 and r.text:
                return {"success": True, "html": r.text, "error": None}
            return {
                "success": False,
                "html": "",
                "error": f"httpx: HTTP {r.status_code}",
            }
    except Exception as e:
        return {
            "success": False,
            "html": "",
            "error": f"httpx: {type(e).__name__}: {e}",
        }


def scrape(url: str, timeout: int = 60) -> dict:
    """Sync entry — wraps the async core via asyncio.run."""
    if not timeout:
        timeout = get_timeout("httpx", 60)
    try:
        return asyncio.run(_async_scrape(url, timeout))
    except Exception as e:
        return {
            "success": False,
            "html": "",
            "error": f"httpx: {type(e).__name__}: {e}",
        }
