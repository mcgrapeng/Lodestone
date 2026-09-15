# -*- coding: utf-8 -*-
"""radar_pkg.detect — 本机能力扫描(平台表 + detect_local_skills + CLI 探测)。"""
import json
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

from radar_pkg import core
from radar_pkg.core import _parse_frontmatter_desc, FRONTMATTER_DESC
from radar_pkg.gh import _gh_repo_meta
from radar_pkg.match import (
    _load_repo_index,
    _owner_repo_from_link_target,
    invalidate_repo_index,
)

_SKILL_PLATFORM_PATHS: dict[str, str] = {
    "claude": "~/.claude/skills",
    "codex": "~/.codex/skills",
    "opencode": "~/.config/opencode/skills",
    "easycode": "~/.easycode/skills",
}
try:  # ponytail: config.toml 覆盖/扩展 — 解析失败静默回退内置表(爬虫配置同理)
    import tomllib as _tomllib

    with open(core.ROOT / "config.toml", "rb") as _f:
        _cfg = _tomllib.load(_f)
    _install_cfg = _cfg.get("install") or {}
    for _k, _v in (_install_cfg.get("platforms") or {}).items():
        if isinstance(_v, str) and _v.strip():
            _SKILL_PLATFORM_PATHS[_k.strip()] = _v.strip()
    # 默认安装平台(前端初始勾选由前端常量定义;此处管 API 不传 targets 时)
    _dt = _install_cfg.get("default_targets")
    if isinstance(_dt, list) and _dt:
        _DEFAULT_INSTALL_TARGETS = tuple(
            t for t in (str(x).strip() for x in _dt) if t in _SKILL_PLATFORM_PATHS
        )
    else:
        _DEFAULT_INSTALL_TARGETS = ("claude",)
except Exception:
    _DEFAULT_INSTALL_TARGETS = ("claude",)

SKILL_PLATFORM_LABELS = {
    "claude": "Claude Code",
    "codex": "Codex",
    "opencode": "OpenCode",
    "easycode": "EasyCode",
}

SUPPORTED_CLIS = tuple(_SKILL_PLATFORM_PATHS)  # 安装 targets 校验 + 默认顺序

def _skills_root_for(cli: str) -> Path:
    """Map CLI name → skills directory (single source: SKILL_PLATFORM_PATHS)."""
    p = _SKILL_PLATFORM_PATHS.get(cli)
    if not p:
        raise ValueError(
            f"unsupported CLI: {cli!r}. Supported: {', '.join(SUPPORTED_CLIS)}"
        )
    return Path(p).expanduser()

_LOCAL_SCAN_TTL = 60

_local_scan_cache: dict = {"ts": 0.0, "data": None}

_local_scan_lock = threading.Lock()

def invalidate_local_scan():
    with _local_scan_lock:
        _local_scan_cache["ts"] = 0.0
        _local_scan_cache["data"] = None

def detect_local_skills(force: bool = False):
    """Scan all forms of installed Claude/Codex capabilities.
    Returns: {
      "skills":   {name: {claude, codex, url, desc_zh, desc_en, topics, stars, source}},
      "commands": {name: {claude}},
      "agents":   {name: {claude}},
      "plugins":  [{name, marketplace, version, install_path}],
    }
    Source priority: PG match → sidecar origin → SKILL.md frontmatter → none
    Cached for 60s — pass force=True to rescan (install/uninstall paths auto-invalidate).
    """
    now = time.time()
    with _local_scan_lock:
        if (
            not force
            and _local_scan_cache["data"] is not None
            and now - _local_scan_cache["ts"] < _LOCAL_SCAN_TTL
        ):
            return _local_scan_cache["data"]
    out = {"skills": {}, "commands": {}, "agents": {}, "plugins": []}

    # ponytail: build lookup from PostgreSQL — match by repo segment (last path component). DB is source of truth (latest.json deprecated).
    by_repo = _load_repo_index()

    # ponytail: build lookup from sidecar — covers installs not in latest.json
    by_origin = {"skills": {}, "commands": {}, "agents": {}, "plugins": {}}
    if core.SKILL_ORIGINS.exists():
        try:
            data = json.loads(core.SKILL_ORIGINS.read_text())
            for kind in ("skills", "commands", "agents", "plugins"):
                for key, info in (data.get(kind) or {}).items():
                    by_origin[kind][key] = info
        except (OSError, ValueError):
            pass
    # ponytail: index by bare name for commands/agents (file stem matches name)
    cmd_origin_by_name = by_origin["commands"]
    agent_origin_by_name = by_origin["agents"]
    plugin_origin_by_key = by_origin["plugins"]  # plugin key format: name@marketplace

    # skills dirs — 遍历全平台表(2026-09 修复:此前硬编码 claude/codex,
    # 装到 opencode 的 ~250 个技能全部漏检)
    for label, path_expr in _SKILL_PLATFORM_PATHS.items():
        d = Path(path_expr).expanduser()
        if not d.exists():
            continue
        try:
            for entry in d.iterdir():
                if entry.name.startswith("."):
                    continue
                if not (entry.is_dir() or entry.is_symlink()):
                    continue
                meta = out["skills"].setdefault(
                    entry.name,
                    {
                        **{p: False for p in _SKILL_PLATFORM_PATHS},
                        "url": None,
                        "desc_zh": None,
                        "desc_en": None,
                        "topics": [],
                        "stars": 0,
                        "source": "none",
                    },
                )
                meta[label] = True
                # ponytail: 2026-09 — symlink 指向本工具缓存(SKILLS_CACHE/owner__repo)
                # 时直接还原 owner/repo,零歧义且不依赖 sidecar/PG(实测 ecc 的
                # origins.json 无记录,sidecar 兜不住,链接目标才是事实来源)。
                if entry.is_symlink():
                    full = _owner_repo_from_link_target(entry)
                    if full:
                        meta["origin_full"] = full
        except OSError:
            pass

    # ponytail: enrich each skill with desc/url from 3 sources (priority: cache > origin > skillmd)
    for name, meta in out["skills"].items():
        # ponytail: 2026-09 大小写不敏感 — 目录名/symlink 名与 GitHub repo 名大小写
        # 不必一致(实测 opencode/skills/ecc ↔ affaan-m/ECC);索引键已统一小写。
        if name.lower() in by_repo:
            r = by_repo[name.lower()]
            meta.update(
                {
                    "url": r.get("url"),
                    "desc_zh": r.get("desc_zh") or r.get("desc"),
                    "desc_en": r.get("desc"),
                    "topics": r.get("topics") or [],
                    "stars": r.get("stars") or 0,
                    "source": "cache",
                }
            )
        elif name in by_origin["skills"]:
            o = by_origin["skills"][name]
            meta["url"] = o.get("url")
            meta["source"] = "origin"
            # ponytail: installed skill not in our PG — fetch stars/topics live from GitHub so the source card shows real ⭐
            full = (
                f"{o.get('owner')}/{o.get('repo')}"
                if o.get("owner") and o.get("repo")
                else None
            )
            if full:
                gh = _gh_repo_meta(full)
                if gh:
                    meta["stars"] = gh.get("stars") or 0
                    meta["topics"] = gh.get("topics") or []
                    meta["desc_en"] = gh.get("description") or meta.get("desc_en")
                    meta["pushed_at"] = gh.get("pushed_at")
        else:
            for skills_root in [
                Path(p).expanduser() for p in _SKILL_PLATFORM_PATHS.values()
            ]:
                skill_md = skills_root / name / "SKILL.md"
                if skill_md.exists():
                    try:
                        text = skill_md.read_text()
                        m = FRONTMATTER_DESC.search(text)
                        if m:
                            meta["desc_en"] = m.group(1).strip().strip('"').strip("'")
                            meta["source"] = "skillmd"
                    except OSError:
                        pass
                    break

    # ponytail: 2026-09 — 谷歌翻译管线已移除；desc_zh 不再自动翻译，保持空。

    # ponytail: Claude slash commands are *.md files (not subdirs) in commands/
    cmd_dir = Path.home() / ".claude" / "commands"
    if cmd_dir.exists():
        try:
            for f in cmd_dir.iterdir():
                if f.suffix == ".md" and not f.name.startswith("."):
                    origin = cmd_origin_by_name.get(f.stem, {})
                    desc_en = origin.get("desc_en") or _parse_frontmatter_desc(f)
                    out["commands"][f.stem] = {
                        "claude": True,
                        "path": str(f),
                        "url": origin.get("url"),
                        "desc_zh": origin.get("desc_zh"),
                        "desc_en": desc_en,
                    }
        except OSError:
            pass

    # ponytail: Claude subagent definitions are *.md files in agents/
    agent_dir = Path.home() / ".claude" / "agents"
    if agent_dir.exists():
        try:
            for f in agent_dir.iterdir():
                if f.suffix == ".md" and not f.name.startswith("."):
                    origin = agent_origin_by_name.get(f.stem, {})
                    desc_en = origin.get("desc_en") or _parse_frontmatter_desc(f)
                    out["agents"][f.stem] = {
                        "claude": True,
                        "path": str(f),
                        "url": origin.get("url"),
                        "desc_zh": origin.get("desc_zh"),
                        "desc_en": desc_en,
                    }
        except OSError:
            pass

    # ponytail: plugins from installed_plugins.json (v2 schema).
    # GitHub URL priority: sidecar override > known_marketplaces.json dynamic read > none.
    # Reading known_marketplaces.json means we auto-pick-up every marketplace the user has
    # installed — no need to maintain a hardcoded list.
    marketplace_urls: dict[str, str] = {}
    known_mp_file = Path.home() / ".claude" / "plugins" / "known_marketplaces.json"
    if known_mp_file.exists():
        try:
            mp_data = json.loads(known_mp_file.read_text())
            for mp_name, mp_info in (mp_data or {}).items():
                src = mp_info.get("source") or {}
                if src.get("source") == "github" and src.get("repo"):
                    marketplace_urls[mp_name] = f"https://github.com/{src['repo']}"
                elif src.get("source") == "git" and src.get("url"):
                    # ponytail: handle git-clone marketplace (e.g. claude-plugins-official) — strip .git suffix
                    u = src["url"]
                    if u.endswith(".git"):
                        u = u[:-4]
                    marketplace_urls[mp_name] = u
        except (OSError, ValueError):
            pass
    plugins_file = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
    # ponytail: read enabledPlugins from settings.json — only show actually-enabled plugins (skip disabled)
    enabled_set: set[str] = set()
    settings_path = Path.home() / ".claude" / "settings.json"
    if settings_path.exists():
        try:
            s = json.loads(settings_path.read_text())
            for k, v in (s.get("enabledPlugins") or {}).items():
                if v is True:
                    enabled_set.add(k)
        except (OSError, ValueError):
            pass
    if plugins_file.exists():
        try:
            data = json.loads(plugins_file.read_text())
            for plugin_key, installs in (data.get("plugins") or {}).items():
                # ponytail: 2026-09 修复 enabled 误杀 installed — installed_plugins.json
                # 本身就是安装记录;不在 enabledPlugins 只说明「未启用」,不代表「未安装」
                # (实测 ecc@ecc v2.0.0 已装但被此过滤整行跳过,卡片永远不亮)。
                # enabled 如实记录,不再影响是否收录。
                plugin_enabled = not enabled_set or plugin_key in enabled_set
                if "@" in plugin_key:
                    name, marketplace = plugin_key.split("@", 1)
                else:
                    name, marketplace = plugin_key, ""
                inst = (
                    max(installs, key=lambda i: i.get("installedAt", ""))
                    if installs
                    else {}
                )
                origin = plugin_origin_by_key.get(plugin_key, {})
                default_url = marketplace_urls.get(marketplace)
                out["plugins"].append(
                    {
                        "name": name,
                        "marketplace": marketplace,
                        "version": inst.get("version", ""),
                        "install_path": inst.get("installPath", ""),
                        "url": origin.get("url") or default_url,
                        "desc_zh": origin.get("desc_zh"),
                        "desc_en": origin.get("desc_en"),
                        "enabled": plugin_enabled,
                    }
                )
        except (OSError, ValueError, TypeError):
            pass

    # ponytail: MCP servers (context7 / chrome-devtools-mcp / etc) — settings.json mcpServers
    settings_file = Path.home() / ".claude" / "settings.json"
    if settings_file.exists():
        try:
            s = json.loads(settings_file.read_text())
            out["mcp_servers"] = sorted((s.get("mcpServers") or {}).keys())
        except (OSError, ValueError):
            pass

    # ponytail: CLI integrations grouped by installer — drives the "本机 CLI" card.
    out["clis"] = {}

    # ponytail: 2026-09 — macOS-only paths. /opt/homebrew/bin 和 /Applications 是
    # Apple Silicon 默认布局，Linux 上不会崩（Path.exists() 守卫），但用户看不到
    # 「平台不支持 brew/cask」的明确信号——卡里只剩 uv/cargo。显式 sys.platform 守卫。
    if sys.platform == "darwin":
        # brew binaries (symbolic links under /opt/homebrew/bin)
        brew_bin = Path("/opt/homebrew/bin")
        if brew_bin.exists():
            out["clis"]["brew"] = sorted(
                p.name
                for p in brew_bin.iterdir()
                if not p.name.startswith(".") and (p.is_file() or p.is_symlink())
            )

        # Homebrew cask GUI apps in /Applications
        apps_dir = Path("/Applications")
        if apps_dir.exists():
            out["clis"]["cask"] = sorted(
                p.stem for p in apps_dir.iterdir() if p.suffix == ".app"
            )

    # uv tools (parse `uv tool list` — first token per non-separator line)
    # 跨平台可用,不需要守卫
    try:
        uv_out = subprocess.check_output(
            ["uv", "tool", "list"],
            text=True,
            timeout=5,
            stderr=subprocess.DEVNULL,
        )
        out["clis"]["uv"] = [
            line.strip().split()[0]
            for line in uv_out.splitlines()
            if line.strip() and not line.strip().startswith("-")
        ]
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pass

    # cargo extensions (cargo-* binaries in ~/.cargo/bin)
    cargo_bin = Path.home() / ".cargo" / "bin"
    if cargo_bin.exists():
        out["clis"]["cargo"] = sorted(
            p.name for p in cargo_bin.iterdir() if p.name.startswith("cargo-")
        )

    with _local_scan_lock:
        _local_scan_cache["ts"] = time.time()
        _local_scan_cache["data"] = out
    return out

def detect_cli_tools():
    """Run `which` for KNOWN_CLIS, return {name: {path, version}}. Cheap — ~50ms total."""
    out = {}
    for tool in KNOWN_CLIS:
        try:
            r = subprocess.run(
                ["which", tool], capture_output=True, text=True, timeout=2
            )
            if r.returncode != 0:
                continue
            path = r.stdout.strip()
            version = ""
            # ponytail: try common version flags, take first line of first successful output
            for flag in ["--version", "-version", "-V", "version"]:
                try:
                    vr = subprocess.run(
                        [path, flag], capture_output=True, text=True, timeout=2
                    )
                    candidate = (vr.stdout or vr.stderr).strip().split("\n")[0]
                    if vr.returncode == 0 and candidate:
                        version = candidate[:60]
                        break
                except (OSError, subprocess.TimeoutExpired):
                    continue
            out[tool] = {"path": path, "version": version}
        except (OSError, subprocess.TimeoutExpired):
            continue
    return out

KNOWN_CLIS = [
    "rtk",
    "gh",
    "docker",
    "kubectl",
    "helm",
    "terraform",
    "jq",
    "rg",
    "fd",
    "fzf",
    "tmux",
    "git",
    "curl",
    "ffmpeg",
    "aws",
    "gcloud",
    "az",
    "supabase",
    "vercel",
    "wrangler",
]
