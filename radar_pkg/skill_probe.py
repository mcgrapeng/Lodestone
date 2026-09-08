# -*- coding: utf-8 -*-
"""SKILL.md probe — 检测 GitHub 仓库是否为「可作为 skill 安装」的格式。

2026-09: 不是所有 GitHub 项目都支持安装为 skill。Claude Code / Codex CLI 的
skill 格式约定：仓库根或子目录有 SKILL.md（少数项目用 skill.md / SKILL.yaml）。
本模块在爬取期并发探测 GitHub raw 端点，把结果写入 data/skill_probe.json 缓存；
repo 字段 is_skill 由 crawl 读缓存写入快照 / PG，前端据此门控安装按钮。

probed 策略（按优先级，单 repo 至多 3 次 HTTP）：
  1. {branch}/SKILL.md      — Claude/Codex/OpenCode 主流约定
  2. {branch}/skill.md      — 小写变体（少数项目）
  3. {branch}/SKILL.yaml    — yaml frontmatter 形式

每个探测结果都缓存（命中即永远 True/False）；probe_force=True 时全量重测。

缓存键：{full_name}.lower → {is_skill: bool, probed_at, reason}。
raw.githubusercontent.com 无 API 速率限制（区别于 api.github.com），可放心大批量探测。
"""

import json
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from radar_pkg import core

_SKILL_FILES = ("SKILL.md", "skill.md", "SKILL.yaml")

# ponytail: Claude/Codex 生态的「skill 目录」约定 — repo 根没有 SKILL.md，
# 但 /skills/<name>/SKILL.md 下挂着多个技能（如 anthropics/skills）。常见命名
# 抽样探测；找不到时 catalog 形式会被判为非 skill（用户其实想装某一个具体
# skill，不是整个目录）。探测单 repo 最多 3+6 = 9 次 HTTP，全走 raw 端点（无 API 速率限制）。
_SKILL_DIRS = ("skills", ".claude/skills", ".opencode/skills", ".codex/skills")

# 已知常见 skill 名（Claude 官方 + 社区）— 命中即视为 skill catalog。
# 不命中不代表非 skill，可能是命名罕见的私有 skill；catalog 形式项目误判
# 为非 skill 对用户无害（少一个「安装」按钮而已）。
_COMMON_SKILL_NAMES = (
    "pdf",
    "docx",
    "pptx",
    "xlsx",
    "canvas-design",
    "algorithmic-art",
    "frontend-design",
    "document-skills",
    "example-skills",
    "web-testing",
    "mcp-builder",
    "brand-guidelines",
)


def _probe_one(full_name: str, cache: dict) -> bool:
    """探测单个 repo 是否包含 skill 格式。
    三级探测：
      L1 repo 根 — SKILL.md / skill.md / SKILL.yaml（单文件 skill）
      L2 skill 目录 — /skills/<name>/SKILL.md（Claude 官方 skills 约定）
      L3 多 CLI 配置 — .claude/skills/<name>/SKILL.md 等（OpenCode / Codex）
    ponytail: 单 repo 最多 3 + 4*N (N=抽样数) 次 HEAD 请求；并发探测，全走
    raw.githubusercontent.com（无 API 速率限制，可放心大批量）。"""
    key = full_name.lower()
    if key in cache:
        return bool(cache[key].get("is_skill"))

    branch = _resolve_branch(full_name)
    is_skill = False

    # L1: 根目录 SKILL.md / skill.md / SKILL.yaml
    for fname in _SKILL_FILES:
        if _head_ok(f"https://raw.githubusercontent.com/{full_name}/{branch}/{fname}"):
            is_skill = True
            break

    # L2 + L3: 目录约定（根未命中才探测 — 节省预算）
    if not is_skill:
        for d in _SKILL_DIRS:
            for sname in _COMMON_SKILL_NAMES:
                url = f"https://raw.githubusercontent.com/{full_name}/{branch}/{d}/{sname}/SKILL.md"
                if _head_ok(url):
                    is_skill = True
                    break
            if is_skill:
                break

    cache[key] = {
        "is_skill": is_skill,
        "probed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "branch": branch,
    }
    return is_skill


def _resolve_branch(full_name: str) -> str:
    """取仓库 default_branch；失败回退 'main'。"""
    try:
        r = subprocess.run(
            ["gh", "api", f"repos/{full_name}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode == 0:
            info = json.loads(r.stdout)
            b = info.get("default_branch") or "main"
            if isinstance(b, str) and b.strip():
                return b.strip()
    except Exception:
        pass
    return "main"


def _head_ok(url: str, timeout: int = 8) -> bool:
    """HEAD 请求；200 = 存在，404 = 没有；其他（5xx/timeout）= 不确定，按不存在处理。
    ponytail: raw.githubusercontent.com HEAD 是廉价的 — 无响应体，无 rate limit。
    urllib 默认 GET；显式 method='HEAD' 避免拉整篇 README。"""
    try:
        req = urllib.request.Request(url, method="HEAD")
        req.add_header("User-Agent", "lodestone/1.0")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except urllib.error.HTTPError as e:
        return e.code == 200
    except Exception:
        return False


def _load_cache() -> dict:
    """读 data/skill_probe.json — 损坏/缺失返回空 dict。"""
    if not core.SKILL_PROBE_CACHE.exists():
        return {}
    try:
        return json.loads(core.SKILL_PROBE_CACHE.read_text())
    except Exception:
        return {}


def _save_cache(cache: dict) -> None:
    """整文件写一次（dict 在 GIL 下线程安全，但写盘需要串行）。"""
    try:
        core.SKILL_PROBE_CACHE.parent.mkdir(parents=True, exist_ok=True)
        core.SKILL_PROBE_CACHE.write_text(
            json.dumps(cache, ensure_ascii=False, indent=1)
        )
    except OSError as e:
        print(f"  [warn] skill probe cache write failed: {e}", file=sys.stderr)


def probe_skills(
    full_names: list[str], max_workers: int = 8, force: bool = False
) -> dict[str, bool]:
    """探测一组 repo 是否有 SKILL.md；返回 {full_name.lower(): is_skill}。
    ponytail: 增量探测 — 缓存命中的 repo 跳过；未命中并发探测；
    每完成一批（max_workers 个）落盘一次，进程崩溃也不丢进度。"""
    cache = {} if force else _load_cache()
    out: dict[str, bool] = {}
    todo: list[str] = []
    for n in full_names:
        if not n or "/" not in n:
            continue
        k = n.lower()
        if not force and k in cache:
            out[k] = bool(cache[k].get("is_skill"))
        else:
            todo.append(n)

    if todo:
        print(
            f"  · skill probe: {len(todo)} repos to check (cache: {len(out)}/{len(full_names)})"
        )
        completed = 0
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futs = {ex.submit(_probe_one, n, cache): n for n in todo}
            for fut in as_completed(futs):
                n = futs[fut]
                try:
                    is_skill = bool(fut.result())
                except Exception:
                    is_skill = False
                out[n.lower()] = is_skill
                completed += 1
                if completed % 200 == 0:
                    _save_cache(cache)
                    print(
                        f"    ... {completed}/{len(todo)} probed, {sum(1 for v in out.values() if v)} skills so far"
                    )
        _save_cache(cache)
    n_skills = sum(1 for v in out.values() if v)
    print(f"  ✓ skill probe done: {n_skills}/{len(out)} are installable as skills")
    return out


def annotate_repos(repos: list, max_workers: int = 8) -> int:
    """便利方法：探测所有 repo 的 is_skill 字段并写回。
    repos 中 url 含 'github.com' 的才会探测；其他来源（HF/arXiv/MCP）跳过。
    返回成功标注的数量。"""
    github = [
        r["name"]
        for r in repos
        if "github.com" in (r.get("url") or "") and r.get("name")
    ]
    if not github:
        return 0
    results = probe_skills(github, max_workers=max_workers)
    n = 0
    by_name = {r["name"].lower(): r for r in repos if r.get("name")}
    for k, is_skill in results.items():
        if k in by_name:
            by_name[k]["is_skill"] = is_skill
            n += 1
    return n


if __name__ == "__main__":
    # CLI 调试：python3 -m radar_pkg.skill_probe owner/repo [owner/repo ...]
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cache = _load_cache()
    for repo in sys.argv[1:]:
        result = _probe_one(repo, cache)
        print(f"  {repo}: {'SKILL' if result else 'no'}")
    _save_cache(cache)
