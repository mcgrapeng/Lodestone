# -*- coding: utf-8 -*-
"""arXiv recent AI papers — official Atom API, no key, no HTML scraping.

Endpoint: GET http://export.arxiv.org/api/query
    ?search_query=cat:cs.AI+OR+cat:cs.CL+OR+cat:cs.LG
    &sortBy=submittedDate&sortOrder=descending&max_results=N
Returns Atom XML (namespace http://www.w3.org/2005/Atom).

Strategy:
  - 最新提交的 AI 论文（cs.AI 人工智能 / cs.CL 计算语言学 / cs.LG 机器学习）
  - name = "arxiv/<id>" 保证与 GitHub repo 命名空间不冲突（论文不可安装，
    但走同一套翻译 / 分类 / 快照管线）
  - 论文没有星标 — stars=0，score 用提交时间戳（和 MCP registry 同思路），
    hot_now 按 stars 排序时论文自然沉底，分类视图按时间排序时在前
"""

from __future__ import annotations

import datetime
import subprocess
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ElementTree
from typing import Optional


ARXIV_API = "https://export.arxiv.org/api/query"
ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"
# 核心AI分类 + 高相关相邻分类；cs.CV 等按需再加
CATEGORIES_QUERY = "cat:cs.AI OR cat:cs.CL OR cat:cs.LG"


def _http_get(url: str, timeout: int = 30) -> Optional[bytes]:
    """Fetch bytes via urllib, falling back to system curl (macOS cert-chain fix).
    arXiv 要求请求间隔 ≥3s — 我们每次 crawl 只发 1 个请求，天然合规。"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "lodestone/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception:
        pass
    try:
        out = subprocess.run(
            # ponytail: -L 跟随 arXiv 偶发的 http→https 301（不跟随会拿到 0 字节"成功"）
            ["curl", "-q", "-sSL", "--max-time", str(timeout), "-A", "lodestone/1.0", url],
            capture_output=True,
            timeout=timeout + 5,
        )
        if out.returncode == 0 and out.stdout:
            return out.stdout
    except Exception:
        pass
    return None


def _entry_to_repo(entry: ElementTree.Element) -> Optional[dict]:
    """Atom entry → repo-shaped dict（与其余 source 同 shape）。"""
    title = (entry.findtext(f"{ATOM}title") or "").strip().replace("\n", " ")
    abs_url = (entry.findtext(f"{ATOM}id") or "").strip()  # http://arxiv.org/abs/2401.12345v1
    if not title or not abs_url:
        return None
    arxiv_id = abs_url.rstrip("/").rsplit("/abs/", 1)[-1]

    summary = (entry.findtext(f"{ATOM}summary") or "").strip()
    summary = " ".join(summary.split())[:500]  # 压平换行、截断

    published = (entry.findtext(f"{ATOM}published") or "")[:10]   # 2026-09-01
    updated = (entry.findtext(f"{ATOM}updated") or "")[:10]

    # 分类标签（primary_category + category）— 去掉 arxiv 前缀
    topics: list[str] = ["arxiv", "paper"]
    for cat_el in entry.findall(f"{ARXIV_NS}primary_category"):
        pc = (cat_el.get("term") or "").strip()
        if pc:
            topics.append(pc)
    authors = [(a.findtext(f"{ATOM}name") or "").strip()
               for a in entry.findall(f"{ATOM}author")]
    first_author = authors[0] if authors else ""
    if first_author:
        summary = f"{first_author}{' et al.' if len(authors) > 1 else ''} — {summary}"

    # 时间戳做 recency score（与 mcp_registry 同思路），排序时新论文在前
    try:
        dt = datetime.datetime.fromisoformat(
            (entry.findtext(f"{ATOM}published") or "").replace("Z", "+00:00")
        )
        score = int(dt.timestamp())
    except Exception:
        score = 0

    return {
        "name": f"arxiv/{arxiv_id}",
        "full_name": f"arxiv/{arxiv_id}",
        "url": f"https://arxiv.org/abs/{arxiv_id}",
        "description": summary,
        "desc": summary,
        "stars": 0,           # 论文没有星标；hot_now 按 stars 排序自然沉底
        "forks": 0,
        "lang": "Paper",
        "topics": topics[:6],
        "updated": updated or published,
        "pushed": published,
        "score": score,
        "best_category": "arxiv",
        "is_ai_relevant": True,   # cs.AI/CL/LG by construction
        "source": "arxiv",
    }


def fetch_arxiv_recent(max_items: int = 30) -> list:
    """最新 AI 论文。失败返回 []（arXiv 挂了不能阻塞其余源）。

    ponytail: 两个 arXiv 坑 —
    ① search_query 要求空格用 + 分隔、冒号保持原样（%3A/%20 被静默吞掉返回空 feed）
    ② 限速 <3s 间隔的连续请求也会返回空体（HTTP 200, 0 bytes）→ 空响应时
       退避 4s 重试一次，一般就通了。"""
    url = (
        f"{ARXIV_API}?search_query={urllib.parse.quote_plus(CATEGORIES_QUERY, safe=':')}"
        f"&sortBy=submittedDate&sortOrder=descending&max_results={max_items}"
    )
    raw = _http_get(url, timeout=30)
    if not raw:
        import time

        print("  [warn] arXiv: empty response (rate-limit?) — retrying in 4s", file=sys.stderr)
        time.sleep(4)
        raw = _http_get(url, timeout=30)
    if not raw:
        print("  [warn] arXiv: fetch failed (urllib + curl both empty, retried)", file=sys.stderr)
        return []
    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError as e:
        print(f"  [warn] arXiv: XML parse failed: {e}", file=sys.stderr)
        return []
    out = []
    for entry in root.findall(f"{ATOM}entry"):
        repo = _entry_to_repo(entry)
        if repo:
            out.append(repo)
    print(f"  ✓ arXiv: {len(out)} recent AI papers", file=sys.stderr)
    return out


if __name__ == "__main__":
    # 冒烟：python3 -m sources.arxiv_papers
    for r in fetch_arxiv_recent(max_items=5):
        print(f"  {r['name']:<28} {r['pushed']}  {r['desc'][:60]}")
