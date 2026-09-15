# -*- coding: utf-8 -*-
"""radar_pkg.install — 安装/卸载/替换/替换推荐(依赖平台表 detect)。"""
import datetime
import json
import shutil
import sys
import subprocess
from pathlib import Path

from radar_pkg import core, detect
from radar_pkg.core import _repo_slug_from_url
from radar_pkg.detect import (
    _DEFAULT_INSTALL_TARGETS,
    SUPPORTED_CLIS,
    _skills_root_for,
    invalidate_local_scan,
)
from radar_pkg.match import invalidate_repo_index

"""radar_pkg.install — 由 radar.py 搬移(2026-09 架构拆分)。"""
def _git_head_sha(path: Path) -> str | None:
    """Read current HEAD SHA from a git working tree."""
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return None

def _git_pull_fast_forward(path: Path) -> tuple[bool, str]:
    """Fetch + reset to origin/HEAD on a --depth=1 clone. Returns (ok, detail)."""
    try:
        # Unshallow so we can compare against origin; cheap if already shallow.
        # For --depth=1 clones, fetch will get the latest commit only.
        fetch = subprocess.run(
            ["git", "fetch", "--depth=1", "origin", "HEAD"],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if fetch.returncode != 0:
            return False, f"fetch failed: {fetch.stderr.strip()[:120]}"
        reset = subprocess.run(
            ["git", "reset", "--hard", "origin/HEAD"],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if reset.returncode != 0:
            return False, f"reset failed: {reset.stderr.strip()[:120]}"
        return True, "updated"
    except subprocess.TimeoutExpired:
        return False, "pull timeout"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"

def _git_remote_head_sha(url: str) -> str | None:
    """Query the default branch's HEAD SHA via `git ls-remote` (no clone)."""
    try:
        r = subprocess.run(
            ["git", "ls-remote", url, "HEAD"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if r.returncode == 0:
            for line in r.stdout.splitlines():
                parts = line.strip().split()
                if len(parts) == 2 and parts[1] == "HEAD":
                    return parts[0]
    except Exception:
        pass
    return None

def install_skill_from_github(name, url, targets=None, force_update=False):
    """Smart install: clone + symlink + version-aware update.
    Supports Claude Code / Codex / OpenCode skills dirs.
    targets: list of CLI names to install into; default = all three.
    force_update: if True, always git pull even if local cache appears fresh.
    Returns dict {target: {status: 'installed'|'updated'|'up_to_date'|'skipped'|'replaced', detail: str}}.
    """
    if targets is None:
        # ponytail: 2026-09 用户决策 — 默认只装 Claude Code(config.toml [install]
        # default_targets 可改);其余平台由前端勾选显式传入
        targets = list(_DEFAULT_INSTALL_TARGETS)
    if (
        not name
        or not all(c.isalnum() or c in "-_." for c in name.replace("/", ""))
        or ".." in name
    ):
        raise ValueError(f"invalid skill name: {name!r}")
    if "/" not in name:
        raise ValueError(f"skill name must be 'owner/repo': {name!r}")
    owner, repo = name.split("/", 1)
    if not all(c.isalnum() or c in "-_." for c in owner) or not all(
        c.isalnum() or c in "-_." for c in repo
    ):
        raise ValueError(f"invalid owner/repo: {name!r}")
    for t in targets:
        if t not in SUPPORTED_CLIS:
            raise ValueError(
                f"unsupported target CLI: {t!r}. Supported: {SUPPORTED_CLIS}"
            )
    if url and not url.startswith("https://github.com/"):
        raise ValueError(f"only github.com urls allowed: {url!r}")
    if not url:
        url = f"https://github.com/{name}"
    else:
        from urllib.parse import urlparse

        path = urlparse(url).path.strip("/")
        if path.endswith(".git"):
            path = path[:-4]
        if path != name:
            raise ValueError(
                f"url {url!r} does not match name {name!r} — refusing to clone mismatch"
            )

    target = core.SKILLS_CACHE / f"{owner}__{repo}"
    cache_state = "fresh"
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["git", "clone", "--depth=1", url, str(target)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git clone failed: {result.stderr.strip()[:200]}")
        cache_state = "cloned"
    elif force_update:
        ok, detail = _git_pull_fast_forward(target)
        cache_state = "updated" if ok else "stale"
    else:
        # ponytail: cheap freshness check — compare local HEAD to remote HEAD via
        # ls-remote (no bandwidth). If they match, skip pull.
        local_sha = _git_head_sha(target)
        remote_sha = _git_remote_head_sha(url)
        if local_sha and remote_sha and local_sha == remote_sha:
            cache_state = "fresh"
        else:
            ok, detail = _git_pull_fast_forward(target)
            cache_state = "updated" if ok else "stale"

    out: dict = {"cache": target, "cache_state": cache_state, "targets": {}}
    for cli in targets:
        skills_root = _skills_root_for(cli)
        skills_root.mkdir(parents=True, exist_ok=True)
        link = skills_root / repo
        action = "installed"
        detail = f"linked → {target.name}"
        if link.is_symlink():
            try:
                if link.resolve() == target.resolve():
                    action = "up_to_date" if cache_state in ("fresh", "cloned") else "updated"
                    detail = f"already linked, cache {cache_state}"
                else:
                    # ponytail: symlink exists but points elsewhere — replace
                    backup = link.with_suffix(link.suffix + ".bak")
                    shutil.move(str(link), str(backup))
                    link.symlink_to(target)
                    action = "replaced"
                    detail = f"was pointing to {link.resolve()}; replaced (backup at {backup.name})"
            except OSError as e:
                action = "skipped"
                detail = f"symlink check failed: {e}"
        elif link.exists():
            # ponytail: real dir/file at the path — back it up so we don't blow
            # away user's local skill by accident.
            backup = link.with_suffix(link.suffix + ".bak")
            shutil.move(str(link), str(backup))
            link.symlink_to(target)
            action = "replaced"
            detail = f"was a real dir; backed up to {backup.name}, replaced with symlink"
        else:
            link.symlink_to(target)
        out["targets"][cli] = {"status": action, "detail": detail, "link": str(link)}

    # ponytail: write sidecar so origin URL survives latest.json roll; idempotent update
    try:
        core.SKILL_ORIGINS.parent.mkdir(parents=True, exist_ok=True)
        origins = {}
        if core.SKILL_ORIGINS.exists():
            try:
                origins = json.loads(core.SKILL_ORIGINS.read_text())
            except (OSError, ValueError):
                origins = {}
        origins.setdefault("skills", {})[repo] = {
            "owner": owner,
            "repo": repo,
            "url": url,
            "installed_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "targets": list(targets),
        }
        core.SKILL_ORIGINS.write_text(json.dumps(origins, ensure_ascii=False, indent=2))
    except OSError as e:
        sys.stderr.write(f"  [warn] sidecar write failed: {e}\n")

    invalidate_local_scan()
    invalidate_repo_index()
    return out

def uninstall_skill(name: str) -> dict:
    """Remove a skill: unlink from ALL platform skills dirs, drop cache dir, remove sidecar entry.
    Returns {removed_links: [paths], cache: path_or_null}.
    2026-09 闭环修复:① 名字校验与 install 契约对齐(owner/repo 或裸 repo 段均可,
    此前字符集不含 '/' 直接 400);② 链接清理遍历平台表全平台(此前硬编码
    claude/codex,opencode/easycode 链接残留导致卸载后「已装」徽标不消失)。"""
    seg = name.split("/")[-1] if "/" in name else name
    if not seg or not all(c.isalnum() or c in "-_." for c in seg) or ".." in seg:
        raise ValueError(f"invalid skill name: {name!r}")
    removed = []
    for skills_root in [
        Path(p).expanduser() for p in detect._SKILL_PLATFORM_PATHS.values()
    ]:
        link = skills_root / seg
        if link.is_symlink() or link.exists():
            try:
                if link.is_symlink():
                    link.unlink()
                elif link.is_dir():
                    shutil.rmtree(link)
                removed.append(str(link))
            except OSError as e:
                sys.stderr.write(f"  [warn] failed to remove {link}: {e}\n")
    # ponytail: also remove the cache clone dir if no other skill symlinks point to it
    if core.SKILL_ORIGINS.exists():
        try:
            origins = json.loads(core.SKILL_ORIGINS.read_text())
            entry = (origins.get("skills") or {}).pop(seg, None)
            if entry:
                owner = entry.get("owner", "")
                repo = entry.get("repo", seg)
                # ponytail: check both new (owner__repo) and legacy (bare repo) cache paths
                candidates = [core.SKILLS_CACHE / f"{owner}__{repo}"]
                if owner:
                    candidates.append(core.SKILLS_CACHE / repo)
                still_used = False
                for r in (origins.get("skills") or {}).values():
                    if r.get("owner") == owner and r.get("repo") == repo:
                        still_used = True
                        break
                for cache_dir in candidates:
                    if cache_dir.exists() and not still_used:
                        try:
                            shutil.rmtree(cache_dir)
                        except OSError:
                            pass
            core.SKILL_ORIGINS.write_text(json.dumps(origins, ensure_ascii=False, indent=2))
        except (OSError, ValueError):
            pass
    invalidate_local_scan()
    invalidate_repo_index()
    return {"removed_links": removed}

def replace_skill(old_name: str, new_name: str, new_url: str = "") -> dict:
    """Install `new_name` then remove `old_name`. Used when user picks a superior alternative.
    ponytail: rollback on uninstall failure — if new installs but old can't be removed,
    we uninstall new to restore pre-call state. Without this the user is left with BOTH
    installed, which is the opposite of "replace"."""
    new_path = install_skill_from_github(new_name, new_url)
    try:
        removed = uninstall_skill(old_name)
    except Exception as e:
        # ponytail: rollback — best-effort, log if rollback itself fails so user sees the state
        sys.stderr.write(
            f"  [warn] replace: uninstall {old_name!r} failed ({e}); rolling back new install\n"
        )
        try:
            uninstall_skill(new_name)
        except Exception as e2:
            sys.stderr.write(
                f"  [ERROR] rollback also failed: {e2}; new still installed at {new_path}\n"
            )
        raise
    return {"new_path": new_path, "old_removed": removed}

def find_skill_replacements(
    local: dict, repos_by_segment: dict, min_anchors: int = 1, min_topic_repos: int = 1
) -> list[dict]:
    """For each installed skill with topics+stars, find uninstalled repos that share
    VERTICAL-domain topics AND look like a stronger alternative.

    Strategy:
      1. Filter out generic topics (claude, codex, ai, agent, llm, graphrag, knowledge-graph, ...) —
         these are universal across many AI tools, so overlapping on them is meaningless. The
         graphrag/knowledge-graph/etc. terms (RAG-flavored) are generic because they're shared
         by every RAG repo regardless of vertical; using them as anchors gave wrong matches
         like LightRAG → graphify.
      2. ponytail: VERTICAL ANCHOR requirement — at least one of the overlap topics must be a
         vertical-specific topic shared by ≤ a few repos in DB. Topics like 'graphrag' or
         'knowledge-graph' don't qualify as anchors even after the generic filter, because the
         overlap itself could be just two AI buzzwords. Require ≥1 overlap topic that's NOT a
         known "buzzword" (i.e. appears in < threshold repos).
      3. Same-category guard — candidate's best_category MUST match installed's best_category.
      4. Score = specific overlap count × 100 + candidate stars.
      5. Sort candidates by score; require ≥min_topic_repos candidates to confirm a category
         exists before surfacing a replacement.

    Returns [{installed, recommended}]."""
    out = []
    # ponytail: build dynamic anchor topic whitelist — a topic is a "vertical anchor" if
    # fewer than 8 repos in our DB share it. Topics like graphrag/knowledge-graph show up in
    # 4-5 repos but they cross distinct verticals (LightRAG vs graphify), so we additionally
    # exclude RAG-flavored anchors entirely.
    _RAG_FLAVORED_ANCHORS = frozenset(
        {
            "graphrag",
            "knowledge-graph",
            "rag",
            "vector-database",
            "embedding",
            "embeddings",
            "large-language-models",
            "llm-evaluation",
            "llm-memory",
            "agent-memory",
        }
    )
    for name, meta in (local.get("skills") or {}).items():
        url = meta.get("url")
        if not url:
            continue
        inst_topics = set(meta.get("topics") or [])
        inst_specific = inst_topics - _GENERIC_TOPICS
        inst_stars = meta.get("stars") or 0
        if not inst_specific or not inst_stars:
            continue
        # ponytail: vertical anchor — installed must have ≥1 specific topic that is also
        # a real vertical differentiator (not just another AI buzzword).
        inst_anchors = inst_specific - _RAG_FLAVORED_ANCHORS
        if len(inst_anchors) < min_anchors:
            continue
        # ponytail: look up installed skill's best_category from the same PG index
        inst_record = repos_by_segment.get(name) or {}
        inst_cat = inst_record.get("best_category")
        candidates = []
        for r in repos_by_segment.values():
            rseg = r["name"].split("/")[-1]
            rurl = (r.get("url") or "").lower()
            if rseg == name:
                continue
            if rurl and rurl == (url or "").lower():
                continue
            # ponytail: same-domain guard. If installed has a category, candidate must match.
            c_cat = r.get("best_category")
            if inst_cat and c_cat and inst_cat != c_cat:
                continue
            c_topics = set(r.get("topics") or [])
            c_specific = c_topics - _GENERIC_TOPICS
            overlap = inst_specific & c_specific
            # ponytail: vertical anchor — overlap must contain ≥min_anchors TRUE vertical anchor(s)
            # shared between installed and candidate. Pure RAG-flavored overlap
            # (graphrag/knowledge-graph only) doesn't count. This is the SOLE filter; we dropped
            # the old `min_overlap=2` gate because vertical-anchored matches with 1 specific
            # topic (e.g. graphify↔tirth8205/code-review-graph via tree-sitter) are valid.
            anchor_overlap = inst_anchors & c_specific
            if len(anchor_overlap) < min_anchors:
                continue
            c_stars = r.get("stars") or 0
            if c_stars < 200:
                continue
            # ponytail: score favors anchor strength + topic count + stars
            score = (
                len(anchor_overlap) * 200
                + len(overlap) * 50
                + min(c_stars, 50000) // 100
            )
            reasons = [
                f"共享 vertical anchor：{', '.join(sorted(anchor_overlap))}",
                f"共 {len(overlap)} 个特定 topic：{', '.join(sorted(list(overlap))[:4])}",
                f"⭐ {c_stars:,}" + (f" vs 已装 {inst_stars:,}" if inst_stars else ""),
            ]
            if inst_cat and c_cat and inst_cat == c_cat:
                reasons.append(f"同领域：{inst_cat}")
            candidates.append(
                {
                    "name": r["name"],
                    "url": r["url"],
                    "stars": c_stars,
                    "topics": sorted(c_topics),
                    "desc_zh": r.get("desc_zh"),
                    "desc_en": r.get("description"),
                    "overlap": sorted(overlap),
                    "anchors": sorted(anchor_overlap),
                    "reasons": reasons,
                    "score": score,
                }
            )
        if len(candidates) >= min_topic_repos:
            candidates.sort(key=lambda x: x["score"], reverse=True)
            top = candidates[0]
            # ponytail: decide replace vs alongside per installed→recommended pair.
            # "替代" requires ALL three signals to fire — same vertical AND ≥2 anchor overlap
            # AND the recommended is meaningfully stronger. Anything less → "并存" (coexist
            # with the existing install). Conservative on purpose: better to nudge coexistence
            # than to talk the user into uninstalling something that works.
            top_record = repos_by_segment.get(top["name"].split("/")[-1]) or {}
            top_cat = top_record.get("best_category")
            same_cat = bool(inst_cat and top_cat and inst_cat == top_cat)
            strong_overlap = len(top.get("anchors") or []) >= 2
            # ponytail: when inst_stars is 0 (PG 没收录的 skill), (inst or 0)*1.5 = 0,
            # making ANY non-zero candidate "much_stronger" — wildly aggressive. Require a
            # minimum baseline of 100 stars on the installed skill before allowing replace.
            baseline = max(100, (inst_stars or 0) * 1.5)
            much_stronger = top["stars"] > baseline
            mode = (
                "replace"
                if (same_cat and strong_overlap and much_stronger)
                else "alongside"
            )
            out.append(
                {
                    "installed": {
                        "name": name,
                        "url": url,
                        "stars": inst_stars,
                        "topics": sorted(inst_topics),
                        "best_category": inst_cat,
                    },
                    "recommended": {**top, "best_category": top_cat},
                    "alternatives_count": len(candidates),
                    "mode": mode,
                }
            )
    out.sort(key=lambda x: x["recommended"]["score"], reverse=True)
    return out

def set_capability_origin(
    kind: str, name: str, url: str = "", desc_zh: str = "", desc_en: str = ""
):
    """Write/edit GitHub origin for a command/agent/plugin in the sidecar.
    `kind` ∈ {commands, agents, plugins}. For plugins, `name` is the full plugin key (name@marketplace).
    Empty `url` clears the entry. Returns the merged origin dict for this item."""
    if kind not in ("commands", "agents", "plugins"):
        raise ValueError(f"unsupported kind: {kind!r}")
    if not name or "/" in name and kind != "plugins":
        raise ValueError(f"invalid name: {name!r}")
    if url and not url.startswith("https://github.com/"):
        raise ValueError(f"only github.com urls allowed: {url!r}")

    core.SKILL_ORIGINS.parent.mkdir(parents=True, exist_ok=True)
    origins = {}
    if core.SKILL_ORIGINS.exists():
        try:
            origins = json.loads(core.SKILL_ORIGINS.read_text())
        except (OSError, ValueError):
            origins = {}  # ponytail: corrupted sidecar — start fresh

    bucket = origins.setdefault(kind, {})
    if url or desc_zh or desc_en:
        entry = bucket.get(name, {})
        if url:
            entry["url"] = url
        if desc_zh:
            entry["desc_zh"] = desc_zh
        if desc_en:
            entry["desc_en"] = desc_en
        entry["updated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
        bucket[name] = entry
    else:
        bucket.pop(name, None)

    core.SKILL_ORIGINS.write_text(json.dumps(origins, ensure_ascii=False, indent=2))
    invalidate_local_scan()
    invalidate_repo_index()
    return bucket.get(name, {})

def group_capabilities_by_origin(local: dict) -> list[dict]:
    """Bucket skills/commands/agents/plugins by their `url` (source repo). Only items with
    a URL are included — local-only / unknown-source items are dropped per UX rule:
    "if it's from a GitHub repo, show this source card; the rest don't need to be shown".
    Returns [{url, slug, name, counts, items}], where `items` is a flat list of
    {type, name, desc_en, desc_zh, path, url, stars, topics} for drill-in display."""
    bucket: dict[str, dict] = {}
    # ponytail: skills are a dict {name: meta}; commands/agents are same shape; plugins is a list
    sources = [
        (
            "skills",
            [(n, m) for n, m in (local.get("skills") or {}).items() if m.get("url")],
        ),
        (
            "commands",
            [(n, m) for n, m in (local.get("commands") or {}).items() if m.get("url")],
        ),
        (
            "agents",
            [(n, m) for n, m in (local.get("agents") or {}).items() if m.get("url")],
        ),
        (
            "plugins",
            [
                (f"{p['name']}@{p.get('marketplace', '')}", p)
                for p in (local.get("plugins") or [])
                if p.get("url")
            ],
        ),
    ]
    for kind, items in sources:
        for name, entry in items:
            url = entry.get("url")
            slug = _repo_slug_from_url(url)
            grp = bucket.setdefault(
                url,
                {
                    "url": url,
                    "slug": slug,
                    "name": slug,
                    "counts": {"skills": 0, "commands": 0, "agents": 0, "plugins": 0},
                    "items": [],
                },
            )
            grp["counts"][kind] += 1
            grp["items"].append(
                {
                    "type": kind,
                    "name": entry.get("name") or name,
                    "desc_en": entry.get("desc_en"),
                    "desc_zh": entry.get("desc_zh"),
                    "path": entry.get("path") or entry.get("install_path"),
                    "url": url,
                    "stars": entry.get("stars"),
                    "topics": entry.get("topics") or [],
                }
            )
    groups = sorted(bucket.values(), key=lambda g: g["slug"])
    for g in groups:
        g["items"].sort(key=lambda it: (it["type"], it["name"] or ""))
        # ponytail: expose total for the stat tile convenience
        g["total"] = len(g["items"])
    return groups

def install_cli_wrapper(name, command):
    """Create ~/.claude/commands/<name>.md slash command wrapping `command`.

    Security: the generated markdown uses Claude Code's `!`cmd`` syntax which EXECUTES
    the command when the slash command is invoked. So `command` is treated as shell —
    we must reject anything that could redirect, pipe, substitute, or chain.
    ponytail: allowlist = "a single executable token + optional safe flags + safe path args".
    Examples that pass: `claude`, `gh`, `git status --short`, `ls /tmp`, `python3 script.py`
    Examples that fail: `curl x|sh`, `rm -rf ~`, `$(whoami)`, `a; b`, `a && b`, backticks.
    """
    if not name or not all(c.isalnum() or c in "-_." for c in name) or ".." in name:
        raise ValueError(f"invalid command name: {name!r}")
    if not command or len(command) > 200:
        raise ValueError("command must be 1-200 chars")

    # ponytail: shell metacharacter check — reject any of these BEFORE writing to disk.
    # They enable pipe/chain/substitution/redirection that turn this into RCE.
    forbidden = set(";|&$()<>`\\\"'*?[]{}~#\n\r\t")
    bad = sorted({c for c in command if c in forbidden})
    if bad:
        raise ValueError(f"command contains forbidden shell metacharacters: {bad!r}")
    # ponytail: require single executable at start (alnum + _-.+), then whitespace + args.
    # Each arg = same safe charset. No `$VAR`, no `~`, no backticks already blocked above.
    import re as _re

    if not _re.fullmatch(r"[A-Za-z0-9_.\-+]+(?:\s+[A-Za-z0-9_.\-+/=@:]+)*", command):
        raise ValueError(
            f"command must be a single executable + safe args: {command!r}"
        )

    target = Path.home() / ".claude" / "commands" / f"{name}.md"
    if target.exists():
        return str(target)  # idempotent

    target.parent.mkdir(parents=True, exist_ok=True)
    body = f"""---
description: Run `{command}` and stream output
---

# /{name}

Execute `{command}` and explain the result.

!`{command}`
"""
    target.write_text(body, encoding="utf-8")
    invalidate_local_scan()
    invalidate_repo_index()
    return str(target)

_GENERIC_TOPICS = frozenset(
    {
        # AI/agent meta
        "ai",
        "ai-agents",
        "ai-agent",
        "ai-tools",
        "agent",
        "agents",
        "agentic",
        "agentic-ai",
        "agentic-framework",
        "agentic-workflow",
        "llm",
        "llms",
        "large-language-models",
        "machine-learning",
        "deep-learning",
        "generative-ai",
        "genai",
        "rag",
        # RAG/embedding/data layer buzzwords — shared by every RAG-flavored repo, can't be anchors
        "graphrag",
        "knowledge-graph",
        "embedding",
        "embeddings",
        "vector-database",
        "pgvector",
        "gpt",
        "gpt-4",
        "openai-api",
        # vendor names (every Claude/Codex tool has these)
        "anthropic",
        "claude",
        "claude-code",
        "claude-ai",
        "codex",
        "openai",
        "chatgpt",
        "google",
        "gemini",
        "deepseek",
        "qwen",
        "kimi",
        "openclaw",
        # generic IDE/coding tool names
        "opencode",
        "antigravity",
        "kiro",
        "qoder",
        "trae",
        "windsurf",
        "windsurf-ai",
        "cursor",
        "cursor-ai",
        "copilot",
        "command-line",
        # scaffolding
        "skills",
        "agent-skills",
        "skill",
        "obra",
        "superpowers",
        "awesome",
        "awesome-list",
        "awesome-llm-apps",
        "awesome-claude-skills",
        "developer-tools",
        "devtools",
        "tools",
        "cli",
        # languages
        "python",
        "typescript",
        "javascript",
        "rust",
        "go",
        "ruby",
    }
)
