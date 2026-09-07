# -*- coding: utf-8 -*-
"""Scrapy adapter — the OG production-grade Python scraper.

Use case: high-throughput, mature pipeline framework — request/response objects,
built-in retry/middleware/concurrency, robots.txt respect, item pipelines. Heavier
than `httpx` but battle-tested for serious crawls (millions of pages).

GitHub: https://github.com/scrapy/scrapy
Install: pip install scrapy

Architecture note: Scrapy is Twisted-based and doesn't play nicely with asyncio.run
in a tight loop. We isolate it via subprocess — scrapy has a `fetch` command
(`scrapy fetch --no-log URL`) that prints raw HTML to stdout. Cleanest cross-runtime
integration; no reactor conflicts.
"""

import asyncio
import subprocess

from .config_loader import get_timeout


def is_available() -> bool:
    try:
        import scrapy  # noqa: F401  # type: ignore[import-not-found]

        return True
    except ImportError:
        try:
            r = subprocess.run(
                ["which", "scrapy"], capture_output=True, timeout=2
            )
            return r.returncode == 0
        except Exception:
            return False


async def _async_scrape(url: str, timeout: int = 60) -> dict:
    """Fetch via `scrapy fetch` (CLI) — runs Scrapy in a fresh reactor so we don't
    clash with the orchestrator's asyncio loop.
    timeout = seconds (0 → load from config.toml [timeouts].scrapy).
    """
    if not timeout:
        timeout = get_timeout("scrapy", 90)
    try:
        # ponytail: subprocess Scrapy — Scrapy's reactor is singleton and can't be
        # restarted in the same process, hence CLI invocation.
        proc = await asyncio.create_subprocess_exec(
            "scrapy",
            "fetch",
            "-s", "USER_AGENT=Mozilla/5.0 (lodestone/scrapy)",
            url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return {
                "success": False,
                "html": "",
                "error": f"scrapy: timeout after {timeout}s",
            }
        if proc.returncode != 0:
            return {
                "success": False,
                "html": "",
                "error": f"scrapy: exit {proc.returncode}: {stderr.decode(errors='replace')[:120]}",
            }
        html = stdout.decode(errors="replace")
        if not html.strip():
            return {"success": False, "html": "", "error": "scrapy: empty body"}
        return {"success": True, "html": html, "error": None}
    except FileNotFoundError:
        return {
            "success": False,
            "html": "",
            "error": "scrapy: CLI not installed (pip install scrapy)",
        }
    except Exception as e:
        return {
            "success": False,
            "html": "",
            "error": f"scrapy: {type(e).__name__}: {e}",
        }


def scrape(url: str, timeout: int = 60) -> dict:
    """Sync entry — wraps the async core via asyncio.run. Pass 0 to use config default."""
    if not timeout:
        timeout = get_timeout("scrapy", 90)
    try:
        return asyncio.run(_async_scrape(url, timeout))
    except Exception as e:
        return {
            "success": False,
            "html": "",
            "error": f"scrapy: {type(e).__name__}: {e}",
        }