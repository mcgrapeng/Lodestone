# -*- coding: utf-8 -*-
"""URL-aware engine dispatcher — picks the right scraper order per URL pattern.

2026-09 精简：引擎从 14 个收敛到 4 个（httpx → cloudscraper →
playwright_stealth → jina，本地轻 → 本地重 → 云端），编排从"全引擎并行
竞赛、最长 HTML 胜出"改为"分级 fallback：每级结果过质量门，不过才升级
更重的引擎"。dispatcher 的职责随之收敛为两件事：

  1. `select_engines(url)` — 该 URL 家族尝试引擎的顺序（轻→重）。
  2. `quality_marker(url)` — 该 URL 家族"真实页面"的结构特征
     （如 github.com/trending 必须含 N 个 `<article class="Box-row"`）。
     质量门用它判断某级引擎拿到的是真页面还是 bot-check 中间页。

注意：这里列出的引擎只是"愿望顺序"，最终是否运行由 config.toml
`[orchestrator].priority` 白名单决定 —— 不在 priority 里的引擎会被
编排器直接跳过。曾覆盖 reddit/x.com/知乎/B站/小红书的规则已删除：
pipeline 从不抓取这些域名，且它们依赖的引擎（nodriver/drissionpage/
agent_reach）已停用。

Pattern is matched against `urllib.parse.urlparse(url).netloc` (lower-case host).
"""
from __future__ import annotations

import urllib.parse

# ponytail: order matters — list is the engine ladder for that URL family
# (light engines first; the tiered orchestrator only escalates on failure).
# Names must exist in `config.toml [orchestrator].priority` to actually run.
URL_PATTERNS: list[tuple[str, list[str]]] = [
    # github.com — trending / search 都是 SSR，httpx 多数直接命中；
    # 挑战页升级 cloudscraper，再不行上真浏览器，最后云端兜底。
    ("github.com", ["httpx", "cloudscraper", "playwright_stealth", "jina"]),
    # *.github.io — 静态站点，轻量引擎足够
    ("github.io", ["httpx", "jina"]),
    # huggingface.co — 公开 JSON / SSR 页，无需浏览器
    ("huggingface.co", ["httpx", "jina"]),
    # Product Hunt / HackerNews / npm / PyPI / arXiv — 公开 JSON API 或简单 SSR
    ("producthunt.com", ["httpx", "jina"]),
    ("news.ycombinator.com", ["httpx", "jina"]),
    ("npmjs.com", ["httpx", "jina"]),
    ("pypi.org", ["httpx", "jina"]),
    ("arxiv.org", ["httpx", "jina"]),
    # Default (catch-all): 完整分级阶梯
    ("_default", ["httpx", "cloudscraper", "playwright_stealth", "jina"]),
]


# ponytail: content hints — caller's preference for HTML vs markdown return.
# "html" → orchestrator picks longest HTML (default).
# "markdown" → orchestrator prefers engines returning clean markdown (jina).
#   markdown content is usually shorter than full HTML, so we add a markdown-aware
#   fallback: if no HTML result but a markdown result is available, use it.
URL_CONTENT_HINTS: dict[str, str] = {
    "huggingface.co": "markdown",
    "github.io": "markdown",
    "news.ycombinator.com": "markdown",
    "arxiv.org": "markdown",
    "pypi.org": "markdown",
    "npmjs.com": "markdown",
}


# ponytail: 质量门的结构特征 — "拿到的是真页面吗？" 该 URL 家族必须出现的
# HTML 标记及最少出现次数。标记与 radar.py 的解析正则保持一致：
#   - github.com/trending 解析 `<article class="Box-row">`（radar.fetch_github_trending）
#   - github.com/search  解析 `data-view-component` SSR 卡片（_parse_github_search_html）
# 拿不到足够标记 = bot-check 页 / 空壳页 → 质量门不通过 → 升级下一级引擎。
# key 匹配的是 URL 子串（host 或 path），不是 host 精确匹配。
URL_QUALITY_MARKERS: list[tuple[str, str, int]] = [
    ("github.com/trending", '<article class="Box-row"', 5),
    ("github.com/search", "data-view-component", 3),
]


def select_engines(url: str) -> list[str]:
    """Return the engine ladder for this URL. Falls back to _default."""
    try:
        host = (urllib.parse.urlparse(url).netloc or "").lower()
    except Exception:
        return URL_PATTERNS[-1][1]

    # exact host match first
    for pattern, engines in URL_PATTERNS:
        if pattern == "_default":
            continue
        if host == pattern or host.endswith("." + pattern):
            return engines

    return URL_PATTERNS[-1][1]  # _default


def content_hint(url: str) -> str:
    """Return "html" or "markdown" — what the caller prefers for this URL family."""
    try:
        host = (urllib.parse.urlparse(url).netloc or "").lower()
    except Exception:
        return "html"
    for pattern, hint in URL_CONTENT_HINTS.items():
        if host == pattern or host.endswith("." + pattern):
            return hint
    return "html"


def quality_marker(url: str) -> tuple[str, int] | None:
    """Return (html_marker, min_count) for URLs with a known page signature,
    or None when any non-bot-check page is acceptable (generic length gate only)."""
    low = (url or "").lower()
    for needle, marker, minimum in URL_QUALITY_MARKERS:
        if needle in low:
            return marker, minimum
    return None


if __name__ == "__main__":
    for u in [
        "https://github.com/trending?since=daily",
        "https://github.com/search?q=agent&type=repositories",
        "https://github.com/owner/repo",
        "https://huggingface.co/spaces/foo/bar",
        "https://pypi.org/project/httpx/",
        "https://example.com/page",
    ]:
        print(
            f"  {u:<55} → {select_engines(u)} hint={content_hint(u)} "
            f"marker={quality_marker(u)}"
        )
