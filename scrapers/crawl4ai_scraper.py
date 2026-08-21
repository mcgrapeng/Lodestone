# -*- coding: utf-8 -*-
"""Crawl4AI adapter (ported from youzi/adapters/crawl4ai_scraper.py, trimmed to html-only).

Free local LLM-ready crawler (github.com/unclecode/crawl4ai).
Install: pip install crawl4ai && crawl4ai-setup

Exposes both `scrape(url, timeout)` (sync, wraps asyncio.run) and
`_async_scrape(url, timeout)` (the async-safe core for parallel orchestration).
"""

import asyncio

from .config_loader import get_timeout, get_user_agent


def is_available() -> bool:
    try:
        import crawl4ai  # noqa: F401

        return True
    except ImportError:
        return False


async def _async_scrape(url: str, timeout: int = 60) -> dict:
    """Fetch rendered HTML via headless Chromium. timeout = seconds (per-page budget).
    Pass 0 to load the default from config.toml [timeouts].crawl4ai."""
    if not timeout:
        timeout = get_timeout("crawl4ai", 120)
    ua = get_user_agent("crawl4ai", "Mozilla/5.0 (lodestone/crawl4ai)")
    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

        config = BrowserConfig(headless=True, user_agent=ua)
        # ponytail: page_timeout=ms — honors the per-engine budget in parallel mode so a stuck
        # crawl4ai can't hold the orchestrator past its overall deadline.
        run_cfg = CrawlerRunConfig(page_timeout=timeout * 1000)
        async with AsyncWebCrawler(config=config) as crawler:
            result = await crawler.arun(url=url, config=run_cfg)
            html = getattr(result, "html", "") or ""
            if html:
                return {"success": True, "html": html, "error": None}
            return {"success": False, "html": "", "error": "crawl4ai: empty html"}
    except Exception as e:
        return {
            "success": False,
            "html": "",
            "error": f"crawl4ai: {type(e).__name__}: {e}",
        }


def scrape(url: str, timeout: int = 60) -> dict:
    """Sync entry point — wraps the async core via asyncio.run. For CLI / serial use.
    Pass 0 to load the default from config.toml [timeouts].crawl4ai."""
    if not timeout:
        timeout = get_timeout("crawl4ai", 120)
    return asyncio.run(_async_scrape(url, timeout))
