# -*- coding: utf-8 -*-
"""DrissionPage adapter — Chinese-developed Chromium + HTTP dual-mode browser.

Use case: Chinese sites (掘金 / CSDN / 知乎 / 思否) often have stronger
bot-checks; DrissionPage's d.e(drive=False) mode lets the page object
fall back to plain requests on 403, then auto-escalate to Chromium
rendering if needed — saving time on happy paths.

GitHub: https://github.com/g1879/DrissionPage
Docs:    https://drissionpage.cn/
Install: pip install DrissionPage
"""

import asyncio


def is_available() -> bool:
    try:
        from DrissionPage import ChromiumPage, SessionPage  # noqa: F401

        return True
    except ImportError:
        return False


async def _async_scrape(url: str, timeout: int = 60) -> dict:
    """Fetch via DrissionPage's dual mode: try SessionPage (requests) and
    escalate to ChromiumPage if the response looks JS-rendered.
    timeout = seconds.
    """
    try:
        from DrissionPage import SessionPage

        def _do():
            page = SessionPage(timeout=timeout)
            page.get(url)
            html = page.html
            # ponytail: if the page looks like a JS shell (very short body
            # with no main content), escalate to ChromiumPage for full render.
            if not html or len(html) < 500 or "<body" not in html:
                try:
                    from DrissionPage import ChromiumPage

                    page2 = ChromiumPage(timeout=timeout)
                    page2.get(url)
                    html2 = page2.html
                    if html2 and len(html2) > len(html):
                        return {
                            "success": True,
                            "html": html2,
                            "error": None,
                        }
                except Exception:
                    pass
            if html:
                return {"success": True, "html": html, "error": None}
            return {
                "success": False,
                "html": "",
                "error": "drissionpage: empty html",
            }

        return await asyncio.to_thread(_do)
    except Exception as e:
        return {
            "success": False,
            "html": "",
            "error": f"drissionpage: {type(e).__name__}: {e}",
        }


def scrape(url: str, timeout: int = 60) -> dict:
    """Sync entry — wraps the async core via asyncio.run."""
    try:
        return asyncio.run(_async_scrape(url, timeout))
    except Exception as e:
        return {
            "success": False,
            "html": "",
            "error": f"drissionpage: {type(e).__name__}: {e}",
        }
