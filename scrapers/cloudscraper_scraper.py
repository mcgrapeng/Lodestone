# -*- coding: utf-8 -*-
"""cloudscraper adapter — bypasses Cloudflare bot-checks for plain HTTP fetches.

Use case: many sites (including GitHub Trending on some IPs / ranges) get
hit with Cloudflare "Checking your browser..." interstitial. urllib +
requests fail; cloudscraper handles the JS challenge.

GitHub: https://github.com/VeNoMouS/cloudscraper
Install: pip install cloudscraper
"""

import asyncio

from .config_loader import get_timeout, load_config


def is_available() -> bool:
    try:
        import cloudscraper  # noqa: F401

        return True
    except ImportError:
        return False


async def _async_scrape(url: str, timeout: int = 60) -> dict:
    """Fetch URL via cloudscraper (which wraps requests with Cloudflare bypass).
    timeout = seconds (0 → load from config.toml [timeouts].cloudscraper).
    """
    if not timeout:
        timeout = get_timeout("cloudscraper", 90)
    cs_cfg = load_config().get("cloudscraper", {})
    try:
        import cloudscraper

        def _do():
            scraper = cloudscraper.create_scraper(
                browser={
                    "browser": cs_cfg.get("browser", "chrome"),
                    "platform": cs_cfg.get("platform", "linux"),
                    "desktop": cs_cfg.get("desktop", True),
                }
            )
            r = scraper.get(url, timeout=timeout)
            if r.status_code == 200 and r.text:
                return {"success": True, "html": r.text, "error": None}
            return {
                "success": False,
                "html": "",
                "error": f"cloudscraper: HTTP {r.status_code}",
            }

        return await asyncio.to_thread(_do)
    except Exception as e:
        return {
            "success": False,
            "html": "",
            "error": f"cloudscraper: {type(e).__name__}: {e}",
        }


def scrape(url: str, timeout: int = 60) -> dict:
    """Sync entry — wraps the async core via asyncio.run."""
    if not timeout:
        timeout = get_timeout("cloudscraper", 90)
    try:
        return asyncio.run(_async_scrape(url, timeout))
    except Exception as e:
        return {
            "success": False,
            "html": "",
            "error": f"cloudscraper: {type(e).__name__}: {e}",
        }
