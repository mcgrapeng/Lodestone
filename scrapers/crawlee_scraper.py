# -*- coding: utf-8 -*-
"""Crawlee (Apify) adapter — production crawler framework with built-in
queue/retries/proxy rotation/headless browser pool. The de-facto standard
for serious scraping in 2026.

Use case: large-scale crawls needing persistent queues, browser fingerprinting
rotation, and structured storage. Heaviest dependency in our stack but
most battle-tested.

GitHub: https://github.com/apify/crawlee-python
Install: pip install crawlee

ponytail: 2026-08 — rewritten for crawlee 1.x. The old `BeautifulSoupCrawler`
init signature (`max_requests_per_crawl`, `request_timeout`, `storage_dir`)
was deprecated; the new options live in `HttpCrawlerOptions` (TypedDict).
We pass only the universal HTTP-level options the orchestrator actually uses.
"""

import asyncio
import tempfile

from .config_loader import get_timeout


def is_available() -> bool:
    try:
        import crawlee  # noqa: F401  # type: ignore[import-not-found]
        return True
    except ImportError:
        return False


async def _async_scrape(url: str, timeout: int = 60) -> dict:
    """Fetch via Crawlee's BeautifulSoupCrawler (lightest Crawlee variant).
    timeout = seconds (0 → load from config.toml [timeouts].crawlee).
    """
    if not timeout:
        timeout = get_timeout("crawlee", 90)

    def _do():
        try:
            from crawlee.crawlers import BeautifulSoupCrawler  # type: ignore
        except ImportError:
            try:
                from crawlee.beautifulsoup_crawler import BeautifulSoupCrawler  # type: ignore
            except ImportError:
                return {
                    "success": False,
                    "html": "",
                    "error": "crawlee: BeautifulSoupCrawler not exposed in this version",
                }
        try:
            from crawlee import Request  # type: ignore
        except ImportError:
            Request = None  # type: ignore

        with tempfile.TemporaryDirectory() as tmp:
            captured_html: dict = {"html": ""}

            async def _run():
                # ponytail: 2026-08 — only pass options that exist across crawlee 0.x
                # and 1.x. The 1.x options object has different field names; we keep
                # it minimal and let crawlee defaults handle the rest.
                try:
                    crawler = BeautifulSoupCrawler(
                        max_requests_per_crawl=1,
                    )
                except TypeError:
                    # 1.x — needs HttpCrawlerOptions
                    crawler = BeautifulSoupCrawler()

                @crawler.router.default_handler
                async def handler(context) -> None:
                    # BeautifulSoupCrawler in crawlee 1.x parses the response into a
                    # BeautifulSoup object stored at `context.soup`. `context.page` is
                    # None (Playwright-style attribute doesn't exist). The HTTP
                    # response is at `context.http_response` for raw HTML.
                    soup = getattr(context, "soup", None)
                    if soup is not None:
                        captured_html["html"] = str(soup)
                        return
                    http_resp = getattr(context, "http_response", None)
                    if http_resp is not None:
                        try:
                            captured_html["html"] = http_resp.read().decode(
                                "utf-8", errors="replace"
                            )
                        except Exception:
                            captured_html["html"] = str(http_resp)
                        return
                    if hasattr(context, "html"):
                        captured_html["html"] = context.html

                # ponytail: 2026-08 — crawlee 1.x requires Request to have a
                # `unique_key`. Use the URL itself as the key (single-request
                # crawl, so collisions don't matter). Falls back to plain URL
                # if Request is missing or the constructor doesn't take `url=`.
                if Request is not None:
                    try:
                        await crawler.run(
                            [Request(url=url, unique_key=url)]
                        )
                    except TypeError:
                        try:
                            await crawler.run([Request(url=url)])
                        except Exception:
                            await crawler.run([url])
                    except Exception:
                        # ValidationError or similar — try plain URL
                        await crawler.run([url])
                else:
                    await crawler.run([url])

            try:
                # ponytail: Crawlee uses asyncio internally; run in a fresh loop.
                asyncio.run(_run())
            except Exception as e:
                return {
                    "success": False,
                    "html": "",
                    "error": f"crawlee: {type(e).__name__}: {e}",
                }
            if captured_html["html"]:
                return {"success": True, "html": captured_html["html"], "error": None}
            return {
                "success": False,
                "html": "",
                "error": "crawlee: empty result (handler never captured)",
            }

    try:
        return await asyncio.to_thread(_do)
    except Exception as e:
        return {
            "success": False,
            "html": "",
            "error": f"crawlee: {type(e).__name__}: {e}",
        }


def scrape(url: str, timeout: int = 60) -> dict:
    """Sync entry — wraps the async core via asyncio.run. Pass 0 to use config default."""
    if not timeout:
        timeout = get_timeout("crawlee", 90)
    try:
        return asyncio.run(_async_scrape(url, timeout))
    except Exception as e:
        return {
            "success": False,
            "html": "",
            "error": f"crawlee: {type(e).__name__}: {e}",
        }