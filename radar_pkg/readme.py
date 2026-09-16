# -*- coding: utf-8 -*-
"""README 抓取 + 缓存 + 同 topic 竞品匹配。

2026-09 重构：旧 Google Translate 管线（desc_zh 一句话翻译 / README 分段翻译 /
/api/repo/<name>/readme 按需翻译）已整体移除 — 本网络到 translate.googleapis.com
不可达，每次 crawl 白烧 ~12 分钟超时且产出为空。中文 5 桶内容现在只有两条路：
宿主 LLM 经 /api/save_summary_batch 回写，或配置 ANTHROPIC_API_KEY /
OPENAI_API_KEY / OLLAMA_HOST 走 llm_analyze。本模块只负责给后者备料：
抓 README 存 raw_md 缓存 + 纯本地 topic 重叠匹配 competitive 桶。
"""
from __future__ import annotations

import datetime
import json
import subprocess
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from radar_pkg import core

_CACHE_LOCK = threading.Lock()


def _fetch_readme_from_github(
    full_name: str, max_chars: int = 12000
) -> tuple[str, str] | None:
    """Fetch README.md from GitHub raw for owner/repo. Returns (text, source_url) or None.
    Try common README filenames in order — README.md / readme.md / README.rst."""
    candidates = ["README.md", "readme.md", "README.rst", "README.txt"]
    # ponytail: GitHub raw URL is owner/repo/HEAD/<file>. Use gh CLI to find the
    # default branch first, then raw URL.
    try:
        r = subprocess.run(
            ["gh", "api", f"repos/{full_name}"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if r.returncode != 0:
            return None
        info = json.loads(r.stdout)
        branch = info.get("default_branch", "main")
    except Exception:
        branch = "main"
    for fname in candidates:
        url = f"https://raw.githubusercontent.com/{full_name}/{branch}/{fname}"
        # ponytail: macOS Python lacks system certs (same issue as HF fetch).
        # Try urllib first, fall back to system curl which uses OS keychain.
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "lodestone/1.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            if raw.strip():
                return raw[:max_chars], url
        except Exception:
            pass
        try:
            out = subprocess.run(
                [
                    "curl",
                    "-q",
                    "-sSL",
                    "--max-time",
                    "20",
                    "-A",
                    "lodestone/1.0",
                    url,
                ],
                capture_output=True,
                text=True,
                timeout=25,
            )
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout[:max_chars], url
        except Exception:
            pass
    return None


def fetch_and_cache_readmes(repos: list, max_workers: int = 6) -> int:
    """为 GitHub repos 抓 README，raw_md 写入 README_ZH_CACHE（llm_analyze 备料）。
    缓存已有 raw_md 的跳过；失败静默。写回时保留磁盘上已有的 sections /
    analysis_5d 桶数据（宿主 LLM 写 5 桶不能被覆盖丢）。
    返回缓存里 raw_md 的总条数。任何失败不阻塞爬取主流程。"""
    cache: dict = {}
    if core.README_ZH_CACHE.exists():
        try:
            cache = json.loads(core.README_ZH_CACHE.read_text())
        except Exception:
            cache = {}
    todo = [
        r
        for r in repos
        if "github.com" in (r.get("url") or "")
        and not cache.get((r.get("name") or "").lower(), {}).get("raw_md")
    ]
    print(f"[crawl] readme fetch: {len(todo)} to fetch ({len(cache)} cached entries)")

    # ponytail: 2026-09 — README 阶段发 bar (每完成 N 条打一次)。 之前全程无声,
    # 前端 /api/crawl/progress 拿到 stale 的上一阶段 100%,用户以为卡住。
    try:
        from radar_pkg.progress import bar, done as _done
        _have_bar = True
    except Exception:
        _have_bar = False
    _t_rm = time.monotonic()
    _done_count = 0
    _bar_step = max(10, len(todo) // 30) if todo else 1  # ~30 updates total

    def _fetch_one(r: dict) -> None:
        nonlocal _done_count
        full_name = r.get("name") or ""
        if "/" not in full_name:
            return
        fetched = _fetch_readme_from_github(full_name)
        if not fetched:
            return
        raw_md, source_url = fetched
        # 只更新备料字段 — sections / analysis_5d 留给磁盘合并，避免覆盖宿主 LLM 桶
        entry = cache.setdefault(full_name.lower(), {})
        entry.update(
            {
                "raw_md": raw_md[:6000],
                "source_url": source_url,
                "fetched_at": datetime.datetime.now().isoformat(timespec="seconds"),
            }
        )
        _done_count += 1
        if _have_bar and (_done_count % _bar_step == 0 or _done_count == len(todo)):
            bar("readmes", _done_count, len(todo), width=32)

    if todo:
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            list(ex.map(_fetch_one, todo))
        if _have_bar:
            _done(f"readme cached: {len(todo)}/{len(todo)} entries ({time.monotonic()-_t_rm:.0f}s)")
    # ponytail: 锁内重读 disk 合并写回。/api/save_summary_batch 也写同一文件,
    # 不重读 disk 直接写 cache 会把并发的新桶数据覆盖丢。
    with _CACHE_LOCK:
        try:
            on_disk = (
                json.loads(core.README_ZH_CACHE.read_text())
                if core.README_ZH_CACHE.exists()
                else {}
            )
            for k, v in cache.items():
                on_disk[k] = {**on_disk.get(k, {}), **v}
            tmp = core.README_ZH_CACHE.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(on_disk, ensure_ascii=False, indent=1))
            tmp.replace(core.README_ZH_CACHE)
        except Exception as e:
            print(f"  [warn] readme cache write failed: {e}", file=sys.stderr)
    # 快照侧：intro 桶用 desc 兜底（前端缺桶自然隐藏），competitive 本地匹配注入
    for r in repos:
        if not r.get("summary_sections"):
            intro = r.get("desc") or ""
            r["summary_sections"] = {
                "intro": intro[:400] if intro else "",
                "can_do": "",
                "problem": "",
                "competitive": "",
                "when_to_use": "",
            }
    n_comp = _attach_competitive(repos)
    print(f"[crawl] competitive: filled for {n_comp} repos")
    return sum(1 for e in cache.values() if e.get("raw_md"))


def _attach_competitive(repos: list, max_per_repo: int = 4) -> int:
    """给每个 repo 的 summary_sections.competitive 注入同类项目。
    ponytail: 不靠 LLM,从我们自己的快照里按 topic 重叠度找.
    overlap 相同再比 stars。competitive 是字符串(中文友好列表),不要 list of dict(避免误读为 pros/cons)"""
    pool = [r for r in repos if r.get("name") and r.get("topics")]
    filled = 0
    for r in repos:
        if not r.get("name") or not r.get("topics"):
            continue
        my_topics = set(t.lower() for t in r["topics"])
        my_name = r["name"].lower()
        candidates = []
        for other in pool:
            if other["name"].lower() == my_name:
                continue
            other_topics = set(t.lower() for t in other.get("topics", []))
            overlap = len(my_topics & other_topics)
            if overlap == 0:
                continue
            candidates.append((overlap, other.get("stars", 0), other))
        # sort by (overlap desc, stars desc); take top N
        candidates.sort(key=lambda x: (-x[0], -x[1]))
        chosen = [c[2] for c in candidates[:max_per_repo]]
        if not chosen:
            continue
        names = [c["name"] for c in chosen]
        sec = r.get("summary_sections") or {}
        sec["competitive"] = "同类项目:" + "、".join(names)
        r["summary_sections"] = sec
        filled += 1
    return filled


if __name__ == "__main__":
    # 冒烟自检：不联网，验证「磁盘桶数据在缓存合并后不丢」
    import tempfile
    from pathlib import Path
    from unittest.mock import patch

    with tempfile.TemporaryDirectory() as td:
        disk = {
            "a/b": {"sections": {"intro": "宿主LLM写的桶"}, "analysis_5d": {"what": "x"}}
        }
        p = Path(td) / "readme_zh_cache.json"
        p.write_text(json.dumps(disk, ensure_ascii=False))
        with patch.object(core, "README_ZH_CACHE", p), patch(
            f"{__name__}._fetch_readme_from_github",
            return_value=("# readme", "https://raw.githubusercontent.com/a/b/HEAD/README.md"),
        ):
            n = fetch_and_cache_readmes(
                [{"name": "a/b", "url": "https://github.com/a/b", "desc": "d"}]
            )
        merged = json.loads(p.read_text())
        assert merged["a/b"]["sections"]["intro"] == "宿主LLM写的桶", merged
        assert merged["a/b"]["analysis_5d"]["what"] == "x", merged
        assert merged["a/b"]["raw_md"] == "# readme", merged
        assert n == 1, n
    print("readme.py self-check OK")
