# -*- coding: utf-8 -*-
"""Scrape curated 'awesome-*' repos and extract linked GitHub repos.

ponytail: 2026-09 P2 — bridges the topic-label gap. Many mainstream AI tools
ship without GitHub topics; curated awesome-* lists are the de-facto canonical
index of a downstream architecture. We scrape READMEs and extract owner/repo
pairs from markdown links, then enrich via `radar_pkg.gh._gh_repo_meta`.
"""
from __future__ import annotations

import base64
import json
import re
import subprocess
import sys
from typing import Iterator, Optional

from radar_pkg.gh import _gh_repo_meta


LISTS = [
    ("eugeneyan/awesome-llm", "README.md"),
    ("sindresorhus/awesome", "README.md"),
    ("openai/openai-cookbook", "README.md"),
    ("anthropics/skills", "README.md"),
    ("mksglu/context-mode", "README.md"),
    ("Tencent/WeKnora", "README.md"),
    ("alibaba/open-code-review", "README.md"),
    ("dair-ai/awesome-prompts", "README.md"),
    ("filipecaldeira/Awesome-LLM-Workflow-Optimization", "README.md"),
    ("alvinreal/awesome-mlops", "README.md"),
    ("GenerativeAI/awesome-generative-ai", "README.md"),
    ("jasonkneen/awesome-mcp-servers", "README.md"),
    ("warpdotdev/awesome-mcp", "README.md"),
    ("modelcontextprotocol/awesome-mcp-servers", "README.md"),
    ("sahil2807/awesome-coding-agents", "README.md"),
    ("menlaliayoub/awesome-llm-coding-tools", "README.md"),
    ("kaiyuanyanslcv/awesome-rag-papers", "README.md"),
    ("AwesomeLLM/awesome-llm", "README.md"),
    ("GoogleCloudPlatform/awesome-cloud-builders", "README.md"),
    ("mlabonne/llm-course", "README.md"),
]


_GH_REPO_LINK = re.compile(r"https?://github\.com/([A-Za-z0-9][\w.-]*)/([A-Za-z0-9][\w.-]*)")


def _fetch_readme(full_name: str, ref_path: str) -> Optional[str]:
    try:
        r = subprocess.run(
            ["gh", "api", f"repos/{full_name}/contents/{ref_path}"],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            return None
        data = json.loads(r.stdout)
        b64 = data.get("content", "")
        if not b64:
            return None
        return base64.b64decode(b64).decode("utf-8", errors="replace")
    except Exception:
        return None


def _extract_github_links(md: str) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for m in _GH_REPO_LINK.finditer(md):
        owner, repo = m.group(1), m.group(2)
        if owner.endswith((".com", ".io", ".git")) or repo.endswith(".git"):
            continue
        if repo in {"issues", "pulls", "discussions", "wiki", "settings"}:
            continue
        out.add((owner, repo))
    return out


def crawl() -> Iterator[dict]:
    seen: set[str] = set()
    for full_name, ref_path in LISTS:
        print(f"  · awesome: {full_name}", file=sys.stderr)
        md = _fetch_readme(full_name, ref_path)
        if md is None:
            continue
        for owner, repo in _extract_github_links(md):
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
                "source": "awesome_lists",
            }


if __name__ == "__main__":
    # ponytail: manual smoke test — `python3 -m sources.awesome_lists`
    md = (
        "# Test\n"
        "- [Foo](https://github.com/owner1/repo1)\n"
        "- [Bar](https://github.com/owner2/repo2)\n"
        "- Skip: https://github.com/owner1/issues\n"
    )
    links = _extract_github_links(md)
    print(f"extracted: {sorted(links)}")
    assert links == {("owner1", "repo1"), ("owner2", "repo2")}, f"unexpected: {links}"
    print("ok")
