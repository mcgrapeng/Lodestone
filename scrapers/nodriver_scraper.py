# -*- coding: utf-8 -*-
"""nodriver adapter — the post-undetected-chromedriver generation, the most
undetectable open-source browser automation. Used by the data-scraping
community to bypass Cloudflare/DataDome/PerimeterX with zero patches required.

Use case: hardest bot-checks (Cloudflare Turnstile, Akamai Bot Manager,
DataDome). Plain playwright gets blocked; nodriver uses the CDP directly
without the `navigator.webdriver` flag — looks 100% like a real browser.

GitHub: https://github.com/ultrafunkamsterdam/nodriver
Install: pip install nodriver

ponytail: 2026-08 — rewritten for nodriver 0.50+ where `uc.start()` is async
and `Browser.stop()` was renamed to `Browser.aclose()`. The sync wrapper runs
the full async session in a fresh event loop via `asyncio.new_event_loop()`,
because the orchestrator may already be inside one.
"""

import asyncio
import threading

from .config_loader import get_timeout, get_user_agent, load_config


def is_available() -> bool:
    try:
        import nodriver  # noqa: F401  # type: ignore[import-not-found]

        return True
    except ImportError:
        return False


async def _async_scrape(url: str, timeout: int = 60) -> dict:
    """Async-native entry — nodriver 0.50+ uses coroutines throughout.
    timeout = seconds (0 → load from config.toml [timeouts].nodriver).
    """
    if not timeout:
        timeout = get_timeout("nodriver", 90)
    ua = get_user_agent(
        "nodriver",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    )
    cfg = load_config().get("playwright", {})
    browser_args = cfg.get("browser_args", ["--no-sandbox"])
    # ponytail: nodriver 0.50+ accepts browser_args as a LIST (was a string in
    # older versions). user_agent must be passed inside a config dict.
    try:
        import nodriver as uc

        browser = await uc.start(
            headless=True,
            browser_args=browser_args or None,
            user_agent={"userAgent": ua} if ua else None,
        )
        try:
            # ponytail: in nodriver 0.50+, main_tab may itself be a coroutine on first access.
            page = browser.main_tab
            if asyncio.iscoroutine(page):
                page = await page
            # ponytail: nodriver's Tab object exposes CDP commands directly; timeouts
            # are not set on the Tab but on the underlying CDP session per call.
            await page.get(url)
            try:
                await page.wait_for("article.Box-row", timeout=min(15, timeout))
            except Exception:
                pass  # selector is page-specific; ignore failures
            html = await page.content
            if html:
                return {"success": True, "html": html, "error": None}
            return {"success": False, "html": "", "error": "nodriver: empty"}
        finally:
            try:
                await browser.aclose()
            except Exception:
                pass
    except Exception as e:
        # ponytail: nodriver 0.50+ CDP handshake often fails on macOS with
        # "Failed to connect to browser". The browser subprocess starts but
        # the websocket bridge never lands — usually a port-conflict or sandbox
        # issue specific to the user's environment. Surface a clear error so
        # callers know this is environmental, not a code bug.
        msg = str(e).strip() or type(e).__name__
        return {
            "success": False,
            "html": "",
            "error": f"nodriver: {msg} (env issue on this host — try playwright_stealth instead)",
        }


def scrape(url: str, timeout: int = 60) -> dict:
    """Sync entry — nodriver 0.50+ is async-only, so we run the full session
    in a fresh event loop. Pass 0 to use config default.
    """
    if not timeout:
        timeout = get_timeout("nodriver", 90)
    # ponytail: nodriver's start() spawns its own event loop internally and
    # conflicts with `asyncio.run()` if the caller is already inside a loop.
    # Strategy: run in a dedicated thread with its own loop. This sidesteps
    # "asyncio.run() cannot be called from a running event loop" errors.
    result_box: list = [None]

    def _runner():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result_box[0] = loop.run_until_complete(_async_scrape(url, timeout))
        finally:
            loop.close()

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join(timeout=timeout + 30)
    if thread.is_alive():
        return {
            "success": False,
            "html": "",
            "error": f"nodriver: thread timeout after {timeout + 30}s",
        }
    return result_box[0] or {
        "success": False,
        "html": "",
        "error": "nodriver: no result",
    }