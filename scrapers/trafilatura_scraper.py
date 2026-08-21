# -*- coding: utf-8 -*-
"""Trafilatura adapter — best-in-class main-content extraction from HTML.

Use case: scrape README pages, blog posts, documentation — produces clean
markdown/text that beats regex when the HTML is messy or nested.

GitHub: https://github.com/adbar/trafilatura
Install: pip install trafilatura
"""

import asyncio


def is_available() -> bool:
    try:
        import trafilatura  # noqa: F401

        return True
    except ImportError:
        return False


async def _async_scrape(url: str, timeout: int = 60) -> dict:
    """Fetch URL via trafilatura (which uses its own session) and extract
    main content as markdown. Returns dict with markdown + metadata.

    ponytail: trafilatura is sync (uses requests-html under the hood); wrap in
    to_thread so it doesn't block the orchestrator's event loop. The result
    `markdown` is the cleaned main content; UI may surface it as a 'content'
    alternative to raw HTML when the page is JS-rendered.
    """
    try:
        import trafilatura

        def _do():
            downloaded = trafilatura.fetch_url(url)
            if not downloaded:
                return {
                    "success": False,
                    "html": "",
                    "error": "trafilatura: fetch failed",
                }
            markdown = (
                trafilatura.extract(
                    downloaded,
                    output_format="markdown",
                    include_links=True,
                    include_images=False,
                    with_metadata=True,
                    favor_recall=True,
                )
                or ""
            )
            html = downloaded  # keep raw html so downstream parsers can still regex over it
            if markdown:
                return {
                    "success": True,
                    "html": html,
                    "markdown": markdown,
                    "error": None,
                }
            return {
                "success": False,
                "html": html,
                "error": "trafilatura: empty content",
            }

        return await asyncio.to_thread(_do)
    except Exception as e:
        return {
            "success": False,
            "html": "",
            "error": f"trafilatura: {type(e).__name__}: {e}",
        }


def scrape(url: str, timeout: int = 60) -> dict:
    """Sync entry — wraps the async core via asyncio.run."""
    try:
        return asyncio.run(_async_scrape(url, timeout))
    except Exception as e:
        return {
            "success": False,
            "html": "",
            "error": f"trafilatura: {type(e).__name__}: {e}",
        }
