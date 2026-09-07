# -*- coding: utf-8 -*-
"""Playwright + stealth adapter — Chromium with anti-bot-detection patches.

Use case: GitHub Trending sometimes serves a "challenge" page when the IP
range looks like a datacenter. playwright-stealth patches the browser
fingerprint (canvas, navigator.webdriver, languages) to look human.

GitHub: https://github.com/AtuboDadat/playwright_stealth (most maintained fork)
Install: pip install playwright-stealth && playwright install chromium
"""

import asyncio

from .config_loader import get_timeout, get_user_agent, load_config

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def is_available() -> bool:
    try:
        from playwright.async_api import async_playwright  # noqa: F401

        try:
            import playwright_stealth  # noqa: F401

            return True
        except ImportError:
            return False
    except ImportError:
        return False


async def _async_scrape(url: str, timeout: int = 60) -> dict:
    """Playwright with stealth patches applied before any page navigation.
    timeout = seconds (0 → load from config.toml [timeouts].playwright_stealth).
    """
    if not timeout:
        timeout = get_timeout("playwright_stealth", 60)
    timeout_ms = timeout * 1000
    ua = get_user_agent("playwright_stealth", _UA)
    pw_cfg = load_config().get("playwright", {})
    browser_args = pw_cfg.get(
        "browser_args",
        ["--no-sandbox", "--disable-blink-features=AutomationControlled"],
    )
    headless = pw_cfg.get("headless", True)
    try:
        from playwright.async_api import async_playwright
        # ponytail: playwright_stealth v2+ switched from `stealth_async(page)` to
        # `Stealth().apply_stealth_async(page_or_context)` — older name is gone.
        from playwright_stealth import Stealth

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=headless,
                args=browser_args,
            )
            try:
                context = await browser.new_context(
                    user_agent=ua,
                    viewport={"width": 1920, "height": 1080},
                    locale="en-US",
                )
                page = await context.new_page()
                # ponytail: apply stealth patches BEFORE first navigation
                await Stealth().apply_stealth_async(page)
                page.set_default_timeout(timeout_ms)
                await page.goto(url, wait_until="domcontentloaded")
                try:
                    await page.wait_for_selector("article.Box-row", timeout=15000)
                except Exception:
                    pass
                html = await page.content()
                if html:
                    return {"success": True, "html": html, "error": None}
                return {
                    "success": False,
                    "html": "",
                    "error": "playwright_stealth: empty html",
                }
            finally:
                await browser.close()
    except Exception as e:
        return {
            "success": False,
            "html": "",
            "error": f"playwright_stealth: {type(e).__name__}: {e}",
        }


def scrape(url: str, timeout: int = 60) -> dict:
    """Sync entry — wraps the async core via asyncio.run. Pass 0 to use config default."""
    if not timeout:
        timeout = get_timeout("playwright_stealth", 60)
    return asyncio.run(_async_scrape(url, timeout))
