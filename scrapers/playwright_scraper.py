# -*- coding: utf-8 -*-
"""Playwright adapter (ported from youzi/adapters/playwright_scraper.py, trimmed to html-only).

Real Chromium via Playwright — most reliable for JS-heavy / bot-checked pages.
Install: pip install playwright && playwright install chromium

Exposes both `scrape(url, timeout)` (sync, wraps asyncio.run) and
`_async_scrape(url, timeout)` (the async-safe core for parallel orchestration).
"""

import asyncio

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


def is_available() -> bool:
    try:
        from playwright.async_api import async_playwright  # noqa: F401

        return True
    except ImportError:
        return False


async def _async_scrape(url: str, timeout: int = 60) -> dict:
    """Fetch fully-rendered HTML. timeout = seconds."""
    timeout_ms = timeout * 1000
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
            try:
                page = await browser.new_page(
                    user_agent=_UA, viewport={"width": 1920, "height": 1080}
                )
                page.set_default_timeout(timeout_ms)
                await page.goto(url, wait_until="domcontentloaded")
                # ponytail: trending rows render client-side sometimes — wait for one (harmless
                # no-op + timeout on other pages; we return whatever loaded either way)
                try:
                    await page.wait_for_selector("article.Box-row", timeout=15000)
                except Exception:
                    pass
                html = await page.content()
                if html:
                    return {"success": True, "html": html, "error": None}
                return {"success": False, "html": "", "error": "playwright: empty html"}
            finally:
                await browser.close()
    except Exception as e:
        return {
            "success": False,
            "html": "",
            "error": f"playwright: {type(e).__name__}: {e}",
        }


def scrape(url: str, timeout: int = 60) -> dict:
    """Sync entry point — wraps the async core via asyncio.run. For CLI / serial use."""
    return asyncio.run(_async_scrape(url, timeout))
