"""Hacker News top-stories AI filter + linked GitHub repo extraction.

ponytail: 2026-09 P2 — HN front page surfaces new AI tools faster than
GitHub Trending. We pull top 100, filter by AI keywords in title + body,
extract github.com URLs, enrich via _gh_repo_meta.
"""
import json
import re
import urllib.request
from typing import Iterator

from radar_pkg.gh import _gh_repo_meta


TOPSTORY_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{sid}.json"
TIMEOUT = 5

AI_KEYWORDS = {
    "ai", "llm", "gpt", "claude", "openai", "anthropic", "gemini",
    "agent", "embedding", "rag", "transformer", "diffusion",
    "langchain", "huggingface", "ollama", "mcp", "agentic",
    "prompt", "vector", "fine-tune", "fine tune", "finetune",
}


def _get_json(url: str):
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception:
        return None


_GH_URL = re.compile(r"https?://github\.com/([A-Za-z0-9][\w.-]*)/([A-Za-z0-9][\w.-]*)")


_SEEN: set[str] = set()


def _get_count() -> int:
    return len(_SEEN)


def _has_ai_signal(text: str) -> bool:
    if not text:
        return False
    lower = text.lower()
    return any(kw in lower for kw in AI_KEYWORDS)


def _extract_github_urls(text: str) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for m in _GH_URL.finditer(text or ""):
        owner, repo = m.group(1), m.group(2)
        if repo in {"issues", "pulls", "discussions", "wiki", "settings"}:
            continue
        out.add((owner, repo))
    return out


def crawl(max_stories: int = 100) -> Iterator[dict]:
    seen = _SEEN
    ids = _get_json(TOPSTORY_URL) or []
    for sid in ids[:max_stories]:
        item = _get_json(ITEM_URL.format(sid=sid))
        if not item:
            continue
        title = item.get("title", "") or ""
        body = item.get("text", "") or ""
        if not _has_ai_signal(title + " " + body):
            continue
        for owner, repo in _extract_github_urls(title + " " + body):
            full = f"{owner}/{repo}"
            if full in seen:
                continue
            seen.add(full)
            meta = _gh_repo_meta(full)
            if meta is None:
                continue
            yield {
                "name": full,
                "url": meta.get("url") or f"https://github.com/{full}",
                "description": meta.get("description"),
                "topics": meta.get("topics") or [],
                "stars": meta.get("stars") or 0,
                "pushed_at": meta.get("pushed_at"),
                "source": "hackernews_ai",
            }
