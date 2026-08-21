# -*- coding: utf-8 -*-
"""Firecrawl adapter (ported from youzi/adapters/firecrawl_scraper.py, trimmed to html-only).

Remote scraping via REST API or CLI — no local browser needed.
Optional: FIRECRAWL_API_KEY in .env (or install the firecrawl CLI).

Exposes both `scrape(url, timeout)` (sync, wraps asyncio.run — for serial/CLI use) and
`_async_scrape(url, timeout)` (the async-safe core for parallel orchestration in
scrapers/__init__.py).
"""

import asyncio
import json
import os
import subprocess
import urllib.request

from .config_loader import get_timeout


def is_available() -> bool:
    if os.environ.get("FIRECRAWL_API_KEY"):
        return True
    try:
        r = subprocess.run(["which", "firecrawl"], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


async def _async_scrape(url: str, timeout: int = 60) -> dict:
    """Async-safe core: CLI first (logged-in user), then REST API.
    timeout = seconds (0 → load from config.toml [timeouts].firecrawl).
    Pure sync internally (subprocess + urllib); the orchestrator wraps this in
    asyncio.to_thread() so it doesn't block the event loop."""
    if not timeout:
        timeout = get_timeout("firecrawl", 120)
    # === CLI ===
    try:
        probe = subprocess.run(["which", "firecrawl"], capture_output=True, timeout=5)
        if probe.returncode == 0:
            out = subprocess.run(
                ["firecrawl", "scrape", url, "-f", "html"],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if out.returncode == 0 and out.stdout.strip():
                # ponytail: CLI prepends a "Scrape ID: ..." status line to stdout —
                # drop everything before the actual document starts
                html_out = out.stdout
                idx = min(
                    (
                        i
                        for i in (
                            html_out.find("<!DOCTYPE"),
                            html_out.find("<!doctype"),
                            html_out.find("<html"),
                            html_out.find("<HTML"),
                        )
                        if i >= 0
                    ),
                    default=-1,
                )
                if idx > 0:
                    html_out = html_out[idx:]
                if html_out.strip():
                    return {"success": True, "html": html_out, "error": None}
    except Exception:
        pass

    # === REST API ===
    key = os.environ.get("FIRECRAWL_API_KEY")
    if key:
        try:
            # ponytail: raw html (NOT onlyMainContent) — the trending <article> list IS the page body
            req = urllib.request.Request(
                "https://api.firecrawl.dev/v1/scrape",
                data=json.dumps({"url": url, "formats": ["html"]}).encode(),
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read())
            html = data.get("data", {}).get("html", "")
            if html:
                return {"success": True, "html": html, "error": None}
            return {"success": False, "html": "", "error": "firecrawl: empty html"}
        except Exception as e:
            return {"success": False, "html": "", "error": f"firecrawl: {e}"}

    return {
        "success": False,
        "html": "",
        "error": "firecrawl unavailable (no CLI, no FIRECRAWL_API_KEY)",
    }


def scrape(url: str, timeout: int = 60) -> dict:
    """Sync entry point — wraps the async core via asyncio.run. For CLI / serial use.
    Pass 0 to load the default from config.toml [timeouts].firecrawl."""
    if not timeout:
        timeout = get_timeout("firecrawl", 120)
    try:
        return asyncio.run(_async_scrape(url, timeout))
    except Exception as e:
        return {
            "success": False,
            "html": "",
            "error": f"firecrawl: {type(e).__name__}: {e}",
        }
