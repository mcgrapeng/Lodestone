# -*- coding: utf-8 -*-
"""Jina Reader adapter — the free public `r.jina.ai` endpoint that returns
clean markdown for any URL. Already proxied via agent_reach; exposed as a
dedicated engine so it ranks higher in priority for users who want it.

Use case: fastest path to clean content. No rate limit on free tier for
personal use; no install required; works on JS-heavy pages by virtue of running
Jina's own headless browser in the cloud.

Docs: https://jina.ai/reader/
No install required.
"""

import asyncio
import os
import subprocess

from .config_loader import get_timeout, get_user_agent


def is_available() -> bool:
    # ponytail: r.jina.ai is always available as a public endpoint. Jina API key
    # (env JINA_API_KEY) unlocks higher rate limits if the user has one.
    return True


async def _async_scrape(url: str, timeout: int = 60) -> dict:
    """Fetch via Jina Reader (https://r.jina.ai/<url>) — always available.
    timeout = seconds (0 → load from config.toml [timeouts].jina).
    """
    if not timeout:
        timeout = get_timeout("jina", 45)
    ua = get_user_agent("jina", "Mozilla/5.0 (lodestone/jina)")
    jina_url = f"https://r.jina.ai/{url}"

    def _do():
        import urllib.request

        headers = {
            "User-Agent": ua,
            "X-Return-Format": "html",  # we want HTML, not markdown
            "X-Timeout": str(timeout),
        }
        # ponytail: JINA_API_KEY bumps rate limit (free tier = ~20 req/min).
        key = os.environ.get("JINA_API_KEY")
        if key:
            headers["Authorization"] = f"Bearer {key}"
        # ponytail: macOS Python lacks system certs — try urllib first, then fall
        # back to system `curl` which uses the OS keychain.
        try:
            req = urllib.request.Request(jina_url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            if html:
                return {"success": True, "html": html, "error": None}
            return {"success": False, "html": "", "error": "jina: empty response"}
        except Exception:
            pass
        try:
            cmd = [
                "curl", "-q", "-sS", "--max-time", str(timeout),
                "-A", ua,
                "-H", f"X-Return-Format: html",
                "-H", f"X-Timeout: {timeout}",
            ]
            if key:
                cmd += ["-H", f"Authorization: Bearer {key}"]
            cmd.append(jina_url)
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
            if out.returncode == 0 and out.stdout.strip():
                return {"success": True, "html": out.stdout, "error": None}
            return {
                "success": False,
                "html": "",
                "error": f"jina: curl exit {out.returncode}: {out.stderr.strip()[:80]}",
            }
        except Exception as e:
            return {
                "success": False,
                "html": "",
                "error": f"jina: {type(e).__name__}: {e}",
            }

    try:
        return await asyncio.to_thread(_do)
    except Exception as e:
        return {
            "success": False,
            "html": "",
            "error": f"jina: {type(e).__name__}: {e}",
        }


def scrape(url: str, timeout: int = 60) -> dict:
    """Sync entry — wraps the async core via asyncio.run. Pass 0 to use config default."""
    if not timeout:
        timeout = get_timeout("jina", 45)
    try:
        return asyncio.run(_async_scrape(url, timeout))
    except Exception as e:
        return {
            "success": False,
            "html": "",
            "error": f"jina: {type(e).__name__}: {e}",
        }