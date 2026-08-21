# -*- coding: utf-8 -*-
"""Agent-Reach adapter — social-media-aware web fetcher with 19 channels
(B站 / Twitter / Reddit / YouTube / 小红书 / GitHub Trending / ...).

Use case: any URL the user gives us. Agent-Reach picks the right channel
based on the domain, handles cookie auth for protected sites, and falls
back to its built-in `web` channel (Jina Reader) for everything else.

If Agent-Reach CLI is not installed, we fall back to **Jina Reader
directly** (`https://r.jina.ai/<url>`) — the same backend Agent-Reach
uses for its web channel, so we lose the channel routing but keep the
public free API.

GitHub: https://github.com/Panniantong/Agent-Reach
Install: pip install agent-reach
Agent-Reach setup: agent-reach install --env=auto
"""

import asyncio

from .config_loader import get_timeout, get_user_agent, load_config


def is_available() -> bool:
    try:
        from agent_reach import __version__  # noqa: F401

        return True
    except ImportError:
        # ponytail: even without the Python lib, Jina Reader is always available
        # as a free public API — so we report True (the orchestrator sees this as
        # available, but we use Jina Reader instead of importing agent_reach).
        return True


async def _async_scrape(url: str, timeout: int = 60) -> dict:
    """Fetch via Agent-Reach's web channel (Jina Reader backend).
    Returns clean markdown — ideal for README/docs extraction.
    timeout = seconds (0 → load from config.toml [timeouts].agent_reach).
    """

    def _do():
        ar_cfg = load_config().get("agent_reach", {})
        prefer_lib = ar_cfg.get("prefer_python_lib", True)
        jina_format = ar_cfg.get("jina_format", "markdown")
        # ponytail: Agent-Reach's `web` channel wraps `https://r.jina.ai/<url>`.
        # We call that endpoint directly via urllib (always available) — same
        # backend, no extra dep. If the user has agent_reach installed, we
        # delegate to its library for richer handling.
        if prefer_lib:
            try:
                from agent_reach import AgentReach  # type: ignore

                ar = AgentReach()
                markdown = ar.read(url)
                if markdown:
                    return {
                        "success": True,
                        "html": markdown,
                        "markdown": markdown,
                        "error": None,
                    }
            except Exception:
                pass
        # Fallback: Jina Reader directly. Free public API, returns clean markdown.
        jina_url = f"https://r.jina.ai/{url}"
        req = urllib.request.Request(
            jina_url,
            headers={
                "User-Agent": get_user_agent(
                    "agent_reach", "Mozilla/5.0 (lodestone/agent-reach)"
                ),
                "X-Return-Format": jina_format,
                "X-Timeout": str(timeout),
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            markdown = resp.read().decode("utf-8", errors="replace")
        if markdown:
            return {
                "success": True,
                "html": markdown,
                "markdown": markdown,
                "error": None,
            }
        return {"success": False, "html": "", "error": "agent_reach: empty response"}

    try:
        import urllib.request

        return await asyncio.to_thread(_do)
    except Exception as e:
        return {
            "success": False,
            "html": "",
            "error": f"agent_reach: {type(e).__name__}: {e}",
        }


def scrape(url: str, timeout: int = 60) -> dict:
    """Sync entry — wraps the async core via asyncio.run. Pass 0 to use config default."""
    if not timeout:
        timeout = get_timeout("agent_reach", 60)
    try:
        return asyncio.run(_async_scrape(url, timeout))
    except Exception as e:
        return {
            "success": False,
            "html": "",
            "error": f"agent_reach: {type(e).__name__}: {e}",
        }
