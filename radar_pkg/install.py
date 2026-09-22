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
    """Fetch + reset to origin/HEAD on a --depth=1 clone. Returns (ok, detail).
    ponytail: 2026-09 — fetch 后必须 `git remote set-head origin --auto` 刷新 symbolic ref,
    否则上游改了默认分支名(master → main 等)时 `git reset --hard origin/HEAD` 找不到
    ref,cache 半坏,后续 compute_upgradable 永远报「可升级」但升不动。
    """
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
        # ponytail: 刷新 symbolic ref (HEAD → auto-detect current default branch on origin)
        subprocess.run(
            ["git", "remote", "set-head", "origin", "--auto"],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=10,
        )
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
    ponytail: 2026-09 — 持 INSTALL_LOCK 防止与并发 uninstall / set_capability_origin
    撞 SKILL_ORIGINS 与 symlink。validation 早返回不做(无效输入不该占锁)。
    """
    if targets is None:
        # ponytail: 2026-09 用户决策 — 默认只装 Claude Code(config.toml [install]
        # default_targets 可改);其余平台由前端勾选显式传入
        targets = list(_DEFAULT_INSTALL_TARGETS)
    if not targets:
        # ponytail: 2026-09 P2 — 拒绝空 targets。空列表让 lock 之后的 inner 流程
        # 走 0 次 symlink + sidecar,静默写一份空 sidecar,前端轮询看不到任何状态。
        # validation 早返不占锁,跟 invalid name 同级。
        raise ValueError("targets must be non-empty list of CLI names")
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
    if not core.acquire_named_lock(core.INSTALL_LOCK, core.INSTALL_LOCK_STALE_S):
        raise RuntimeError(
            "another install/upgrade is running — retry in a moment"
        )
    try:
        return _install_skill_from_github_locked(
            name, url, owner, repo, targets, force_update
        )
    finally:
        core.release_named_lock(core.INSTALL_LOCK)


def _install_skill_from_github_locked(
    name, url, owner, repo, targets, force_update
):
    """install_skill_from_github 的临界区 — 调用方必须已持 INSTALL_LOCK。
    拆分出来让 validation 在锁外完成,锁只保护副作用。"""

    target = core.SKILLS_CACHE / f"{owner}__{repo}"
    cache_state = "fresh"
    # ponytail: 2026-09 P5 修复 — 检测半残 clone dir(目录在但不是 git repo,
    # 之前 partial clone 失败留下的)。不直接走 git pull,会报 "not a git repository"
    # 然后 symlink 指向坏 dir,用户看到 installed 但所有 git 操作失败。
    is_broken_dir = (
        target.exists() and not (target / ".git").is_dir()
    )
    if is_broken_dir:
        shutil.rmtree(target, ignore_errors=True)
        raise RuntimeError(
            f"corrupted cache at {target} (missing .git); removed, retry install"
        )
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["git", "clone", "--depth=1", url, str(target)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            # ponytail: 清半残 dir — 否则下次 install 进 elif 分支,在破损 .git 上
            # git pull 报 "not a git repository",symlink 指向坏 dir,用户看到 installed
            # 但 git 都失败。
            shutil.rmtree(target, ignore_errors=True)
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

    # ponytail: write sidecar so origin URL survives latest.json roll; idempotent update.
    # ponytail: 2026-09 P3 修复 — sidecar 写失败时回滚所有刚建的 symlink。sidecar
    # 是关键状态(不可重建),symlink 是派生(可重建);失败处理必须按这个顺序,
    # 否则「装了但系统不知道」 — compute_upgradable 找不到该记录,upgrade 永远跳过。
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
        core.atomic_json_write(core.SKILL_ORIGINS, origins)
    except OSError as e:
        # ponytail: 回滚所有刚建的 symlink(原 dir 我们不动 — 用户可能有真数据)。
        # `.bak` 文件是 install_skill 流程 `replaced` 分支被重命名的旧内容,保留。
        for _cli, info in out.get("targets", {}).items():
            link_str = info.get("link", "")
            if link_str:
                _link = Path(link_str)
                if _link.is_symlink() or _link.exists():
                    try:
                        _link.unlink()
                    except OSError:
                        pass
        raise RuntimeError(f"sidecar write failed: {e}") from e

    invalidate_local_scan()
    invalidate_repo_index()
    return out


# ponytail: 2026-09 — install 中心化三件套。
# upgrade / upgrade-all / preflight 共享 install lock + status 写盘 + log append,
# 不再各自重复。每件 return 一个 dict 描述结果(便于 UI 透出)。

def _load_origins() -> dict:
    if not core.SKILL_ORIGINS.exists():
        return {}
    try:
        return json.loads(core.SKILL_ORIGINS.read_text())
    except Exception:
        return {}


def _save_origins(origins: dict) -> None:
    core.atomic_json_write(core.SKILL_ORIGINS, origins)


def compute_upgradable(
    skills: dict,
    origins: dict | None = None,
    progress_callback=None,
) -> dict:
    """对每个已装 skill (skills[name].source=origin|skillmd) 比 local HEAD vs remote HEAD。

    progress_callback(current, total, latest_name) 可选,每 ~5 个 skill 触发一次,
    让 daemon / 手动 refresh 都能上报进度,前端 banner 可见「5/292 正在检查」。

    返回 {name: {local_sha, remote_sha, upgradable: bool, reason: str}}。
    ponytail: 故意一次查所有 ls-remote 串行 5s/个 → 100 项 ~ 8min,后续可并发。
    MVP 不并发:简单 + 限流友好 + 失败时只丢一项而不是炸全。"""
    if origins is None:
        origins = _load_origins()
    skill_origins = (origins or {}).get("skills") or {}
    out: dict = {}
    # ponytail: 2026-09 P7 修复 — 进度分母只算"实际做了 ls-remote 的 skill",
    # 不算 orphan 裸名(无 origin,直接 continue,无实际工作)。否则用户看到
    # 292/292 (100%) 以为检查完毕,实际 286 个被瞬间跳过,前端进度条完全不准。
    relevant = [
        (n, info) for n, info in (skills or {}).items()
        if n and "/" in n and skill_origins.get(n, {}).get("url")
    ]
    total = len(relevant)
    # ponytail: 2026-09 — 进度上报。daemon 周期跑 / 用户点 "立即重算" 时
    # compute_upgradable 是长耗时操作,前端 banner 需要 current/total 实时反馈。
    # 这里用 try/except 包裹回调防单个 callback 抛错影响 compute 主流程。
    last_reported = 0
    for idx, (name, info) in enumerate(relevant, 1):
        origin = skill_origins.get(name)
        # 总在 relevant 里的都有 origin(上面 filter 过了),但 double-check 防 race
        if not origin or not origin.get("url"):
            continue
        owner, repo = name.split("/", 1)
        cache = core.SKILLS_CACHE / f"{owner}__{repo}"
        if not cache.exists():
            out[name] = {
                "local_sha": None,
                "remote_sha": None,
                "upgradable": False,
                "reason": "cache_missing",
                "url": origin["url"],
            }
            # ponytail: 有 origin 但无 cache(刚装的 skill)— 也算实际工作,上报
            _maybe_report(progress_callback, idx, total, name, last_reported, lambda v: (v, idx))
            last_reported = idx
            continue
        local = _git_head_sha(cache)
        remote = _git_remote_head_sha(origin["url"])
        # ponytail: 任一查不到 → 不假设 upgradable,留 reason 让 UI 显示「无法检查」
        if not local or not remote:
            out[name] = {
                "local_sha": local,
                "remote_sha": remote,
                "upgradable": False,
                "reason": "check_failed",
                "url": origin["url"],
            }
        elif local == remote:
            out[name] = {
                "local_sha": local,
                "remote_sha": remote,
                "upgradable": False,
                "reason": "up_to_date",
                "url": origin["url"],
            }
        else:
            out[name] = {
                "local_sha": local,
                "remote_sha": remote,
                "upgradable": True,
                "reason": "behind",
                "url": origin["url"],
            }
        # ponytail: ls-remote 跑完(本地 cache 存在的)— 这是真正有网络 I/O 的工作,
        # 上报进度。orphan 裸名无 origin 不会进 relevant,不计入分母/分子。
        _maybe_report(progress_callback, idx, total, name, last_reported, lambda v: (v, idx))
        last_reported = idx
    # ponytail: 最后 100% 进度上报(分母若为 0,所有 skill 都无 origin,直接报 0/0)
    if progress_callback and total > 0:
        try: progress_callback(total, total, "")
        except Exception: pass
    elif progress_callback:
        # 无可检查的 skill — banner 不显示进度条,但仍通知 computing=false
        try: progress_callback(0, 0, "")
        except Exception: pass
    return out


def _maybe_report(cb, idx, total, name, last_reported, current_fn):
    """进度上报:每 ~5 个 skill 触发一次,带 try/except 防 callback 抛错影响主流程。
    current_fn:lambda(v)→int,从 v 推 current;v 是回环当前 idx 外的局部变量。"""
    if not cb or idx - last_reported < 5:
        return
    try:
        cb(current_fn(last_reported), total, name)
    except Exception:
        pass


def upgrade_one(name: str) -> dict:
    """升级单个已装 skill:
      1. 拿 install lock
      2. 读 origin → fetch + reset
      3. 强制重建所有平台的 symlink
      4. 写 install_log
      5. 释放锁
    返回 {ok, name, status, detail}。"""
    if not name or "/" not in name:
        return {"ok": False, "name": name, "status": "invalid", "detail": "name 必须 owner/repo"}
    if not core.acquire_named_lock(core.INSTALL_LOCK, core.INSTALL_LOCK_STALE_S):
        return {"ok": False, "name": name, "status": "locked", "detail": "另一个 install/upgrade 正在跑"}
    try:
        origins = _load_origins()
        skill_origins = origins.get("skills") or {}
        origin = skill_origins.get(name)
        if not origin or not origin.get("url"):
            return {"ok": False, "name": name, "status": "no_origin",
                    "detail": "没找到 origin 记录,无法升级"}
        owner, repo = name.split("/", 1)
        cache = core.SKILLS_CACHE / f"{owner}__{repo}"
        if not cache.exists():
            return {"ok": False, "name": name, "status": "cache_missing",
                    "detail": f"本地缓存 {cache} 不存在,先 install"}
        ok, detail = _git_pull_fast_forward(cache)
        if not ok:
            core.append_install_log({"action": "upgrade", "name": name, "ok": False, "detail": detail})
            return {"ok": False, "name": name, "status": "fetch_failed", "detail": detail}
        # ponytail: 2026-09 P3 修复 — fetch 成功后立刻让 cache 反映新 SHA,
        # 否则 5 min 内用户看到旧"可升级"徽标 + 升级按钮被禁用。
        core.invalidate_upgradable_cache_for(name)
        # ponytail: fetch 成功后重建 symlink(用户可能换了 platform 或 link 被破坏)
        targets = origin.get("targets") or list(_DEFAULT_INSTALL_TARGETS)
        link_results = {}
        for cli in targets:
            if cli not in SUPPORTED_CLIS:
                continue
            skills_root = _skills_root_for(cli)
            skills_root.mkdir(parents=True, exist_ok=True)
            link = skills_root / repo
            # ponytail: 2026-09 — 原子 rename + 失败回滚。旧实现 unlink + symlink_to 非原子,
            # symlink_to 失败时 link 已删 → skill 在该平台消失,symlink_to OSError 静默吞掉,
            # 函数仍返 ok=True。修法:rename 是同 fs 原子操作,把旧 link/dir 重命名备份,
            # 再尝试创建新 symlink;失败时 rename 回原位。
            old_backup = None
            if link.is_symlink() or link.exists():
                try:
                    old_backup = link.with_name(f"{link.name}.upgrade-tmp")
                    if old_backup.exists():
                        old_backup.unlink()
                    link.rename(old_backup)
                except OSError as e:
                    # ponytail: 备份失败 — 旧 link 不动,记录错误,继续下一个 platform
                    link_results[cli] = {"status": "skipped", "detail": f"backup rename failed: {e}"}
                    continue
            try:
                link.symlink_to(cache)
                if old_backup is not None:
                    old_backup.unlink(missing_ok=True)
                link_results[cli] = {"status": "linked", "link": str(link)}
            except OSError as e:
                # ponytail: 新 symlink 失败 — 把 backup rename 回去,平台不变
                if old_backup is not None:
                    try:
                        link.unlink(missing_ok=True)
                        old_backup.rename(link)
                    except OSError as rollback_err:
                        # rollback 也失败 — 报双重错,留给人工
                        link_results[cli] = {
                            "status": "rollback_failed",
                            "detail": f"symlink failed: {e}; rollback failed: {rollback_err}",
                        }
                        continue
                link_results[cli] = {"status": "skipped", "detail": str(e)}
        invalidate_local_scan()
        # ponytail: 2026-09 — 反映部分失败。至少一个 platform rollback_failed/失败
        # → ok=False,status=partial;全部成功才 status=upgraded。前端据此切绿/红勾。
        n_linked = sum(1 for r in link_results.values() if r.get("status") == "linked")
        n_skipped = sum(1 for r in link_results.values() if r.get("status") == "skipped")
        n_rollback_failed = sum(
            1 for r in link_results.values() if r.get("status") == "rollback_failed"
        )
        all_ok = n_rollback_failed == 0 and n_skipped == 0 and n_linked > 0
        core.append_install_log({
            "action": "upgrade",
            "name": name,
            "ok": all_ok,
            "linked": n_linked,
            "skipped": n_skipped,
            "rollback_failed": n_rollback_failed,
        })
        return {
            "ok": all_ok,
            "name": name,
            "status": "upgraded" if all_ok else "partial",
            "detail": detail,
            "links": link_results,
        }
    finally:
        core.release_named_lock(core.INSTALL_LOCK)


def upgrade_all(skills: dict, callback=None, upgradable: dict | None = None) -> dict:
    """批量升级。callback(current, total, name, result) 用于进度回调(可选)。
    upgradable: handler 算好的 dict;非 None 时直接用,跳过本地 compute(避免
    handler+subprocess 双算、total 闪烁、GitHub 限流)。
    返回 {upgraded, skipped, failed, total, results: [{name, status, detail}]}。
    ponytail: 串行而非并发 — git ls-remote 是限流重灾区,100 个并发直接 429。
    ponytail: 2026-09 — try/finally + BaseException 兜底。OOM / Ctrl-C / 子进程
    被 kill 时 running=True 会被清掉,前端 banner 不卡死。
    ponytail: 2026-09 P4 修复 — 整批启动时先抢锁,抢不到立刻报错退出,不再让 5→0→0
    静默饿死 banner(旧实现每个 target 抢不到锁就 total-=1,user 看着 banner
    5→4→3→2→1→0 跑完,实际什么都没升)。"""
    started = datetime.datetime.now().isoformat(timespec="seconds")
    # ponytail: 启动时抢锁 — 抢不到说明另一个 install/upgrade 在跑,立刻失败退出。
    # 代价:整批 8 min 持有锁,sync /api/upgrade 期间返 locked 立刻给用户反馈,
    # 比静默饿死好太多。
    if not core.acquire_named_lock(core.INSTALL_LOCK, core.INSTALL_LOCK_STALE_S):
        core.write_install_status(
            running=False, current=0, total=0,
            label="升级全部 (锁定中)", started_at=started,
            finished_at=datetime.datetime.now().isoformat(timespec="seconds"),
            error="另一个 install/upgrade 正在跑,稍后重试",
        )
        return {
            "upgradable": 0, "skipped": 0, "failed": 0, "total": 0,
            "results": [], "error": "another install/upgrade in progress",
        }
    try:
        if upgradable is None:
            upgradable = compute_upgradable(skills)
        targets = [(n, info) for n, info in upgradable.items() if info.get("upgradable")]
        total = len(targets)
        results: list[dict] = []
        upgraded = 0
        skipped = 0
        failed = 0
        # ponytail: 单点写入 total — handler 不再写,subprocess 是唯一 owner。
        core.write_install_status(
            running=True, current=0, total=total,
            label="升级全部", started_at=started,
        )
        for i, (name, _info) in enumerate(targets, 1):
            core.write_install_status(current=i - 1, total=total, label=f"升级 {name}")
            result = upgrade_one(name)
            results.append({"name": name, "ok": result.get("ok"),
                            "status": result.get("status"), "detail": result.get("detail", "")})
            if result.get("ok"):
                upgraded += 1
            elif result.get("status") in ("no_origin", "cache_missing", "locked"):
                # ponytail: 2026-09 P3 修复 — 锁期间 origin 被并发进程删了,
                # 不算 failed/skipped,直接从 total 减去,避免 banner 卡在 ghost skill。
                total -= 1
                core.write_install_status(current=i - 1, total=max(1, total),
                                          label=f"升级 {name} (跳过)")
            else:
                failed += 1
            if callback:
                try:
                    callback(i, total, name, result)
                except Exception:
                    pass
        return {"upgradable": upgraded, "skipped": skipped, "failed": failed, "total": total, "results": results}
    except BaseException as e:
        # ponytail: 包括 KeyboardInterrupt + SystemExit — Ctrl-C / OOM 都走这里。
        # 不抛 — 让 daemon fork 出去的进程静默退出(主进程 Popen 不再读 stdout)。
        core.write_install_status(
            running=False, current=0, total=0,
            label=f"升级全部 (中断:{type(e).__name__})",
            started_at=started,
            finished_at=datetime.datetime.now().isoformat(timespec="seconds"),
            error=f"{type(e).__name__}: {e}",
        )
        # ponytail: 仍然返一份 dict 给可能的 in-process 调用者 — 但 daemon 路径不在乎。
        return {"upgradable": 0, "skipped": 0, "failed": 0, "total": 0,
                "results": [], "error": f"{type(e).__name__}: {e}"}
    finally:
        # ponytail: 成功路径已返 dict;但 finally 必须清 running=False,否则上面
        # return 路径异常时不会走(if 上面的 return 走了,这里再写一次覆盖;BaseException
        # 路径已自己写过,这里也再覆盖保证 idempotent)。
        # 实测 finally 在 try 内的 return 后也会跑 — 标准 Python 语义。
        try:
            from radar_pkg.core import read_install_status
            cur = read_install_status()
            if cur.get("running"):
                core.write_install_status(
                    running=False, current=cur.get("current", 0), total=cur.get("total", 0),
                    label=cur.get("label", "升级全部"),
                    started_at=cur.get("started_at"),
                    finished_at=datetime.datetime.now().isoformat(timespec="seconds"),
                )
        except Exception:
            pass
        # ponytail: 2026-09 P4 — 整批结束释放锁,避免升级期间任何 sync 调用都被卡30 min。
        core.release_named_lock(core.INSTALL_LOCK)

def uninstall_skill(name: str, targets: list[str] | None = None) -> dict:
    """Remove a skill. targets=None: ALL platform skills dirs + cache + sidecar entry
    (legacy behavior). targets=[cli,..]: only unlink those CLIs and prune them from
    the entry's targets list; cache preserved as long as another CLI still references it.
    Returns {ok, removed_links, error?}.
    2026-09 闭环修复:① 名字校验与 install 契约对齐(owner/repo 或裸 repo 段均可,
    此前字符集不含 '/' 直接 400);② 链接清理遍历平台表全平台(此前硬编码
    claude/codex,opencode/easycode 链接残留导致卸载后「已装」徽标不消失);
    ③ FU-3.1 — targets 参数真正按 CLI 区分,不再一锅端。
    ponytail: 2026-09 — 持 INSTALL_LOCK 防止与并发 install/upgrade 撞 SKILL_ORIGINS
    与 symlink。撞锁返 409-like 错误让前端能给用户清晰反馈。"""
    # ponytail: 持锁 — 名字校验先做(避免无效输入占锁)
    seg = name.split("/")[-1] if "/" in name else name
    if not seg or not all(c.isalnum() or c in "-_." for c in seg) or ".." in seg:
        raise ValueError(f"invalid skill name: {name!r}")
    if targets is not None:
        for t in targets:
            if t not in SUPPORTED_CLIS:
                raise ValueError(
                    f"unsupported target CLI: {t!r}. Supported: {SUPPORTED_CLIS}"
                )
    if not core.acquire_named_lock(core.INSTALL_LOCK, core.INSTALL_LOCK_STALE_S):
        return {"ok": False, "error": "另一个 install/upgrade 正在跑,稍后重试"}
    try:
        return _uninstall_skill_locked(seg, targets=targets)
    finally:
        core.release_named_lock(core.INSTALL_LOCK)


def _uninstall_skill_locked(seg: str, targets: list[str] | None = None) -> dict:
    """uninstall_skill 的临界区实现 — 调用方必须已持 INSTALL_LOCK。
    targets=None:全平台全清,跟旧契约一致;targets=[cli,...]:只卸指定 CLI,
    仍被其它 CLI 引用的 entry 保留,cache 不动。"""
    removed = []
    # ponytail: targets=None → 遍历平台表全平台;targets 给定 → 仅遍历指定 CLI
    if targets is None:
        roots = [
            (cli, Path(p).expanduser())
            for cli, p in detect._SKILL_PLATFORM_PATHS.items()
        ]
    else:
        roots = [
            (cli, Path(detect._SKILL_PLATFORM_PATHS[cli]).expanduser())
            for cli in targets
            if cli in detect._SKILL_PLATFORM_PATHS
        ]
    for _cli, skills_root in roots:
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
            skill_map = origins.get("skills") or {}
            # ponytail: 2026-09 — 修复 cache 残留 bug。sidecar key 可能是 "test/e2e-skill"
            # (全名)或 "e2e-skill" (裸名,legacy),但 uninstall 调用方传 seg(裸名)。
            # 必须两种都试 pop,不然 cache 永远留着。
            key = None
            entry = skill_map.get(seg)
            if entry is None:
                for k in list(skill_map.keys()):
                    if k == seg or k.endswith("/" + seg):
                        key = k
                        entry = skill_map[k]
                        break
            else:
                key = seg
            if entry is not None:
                cli_to_remove = set(targets) if targets is not None else None
                if cli_to_remove is None:
                    new_targets = []
                else:
                    # ponytail: per-CLI 卸载 → 保留顺序,只剔除指定 CLI
                    new_targets = [
                        t for t in entry.get("targets", []) if t not in cli_to_remove
                    ]
                if not new_targets:
                    # ponytail: 无残留 CLI → 真删,顺手清 cache
                    skill_map.pop(key)
                    owner = entry.get("owner", "")
                    repo = entry.get("repo", seg)
                    # ponytail: check both new (owner__repo) and legacy (bare repo) cache paths
                    candidates = [core.SKILLS_CACHE / f"{owner}__{repo}"]
                    if owner:
                        candidates.append(core.SKILLS_CACHE / repo)
                    still_used = False
                    for r in skill_map.values():
                        if r.get("owner") == owner and r.get("repo") == repo:
                            still_used = True
                            break
                    for cache_dir in candidates:
                        if cache_dir.exists() and not still_used:
                            try:
                                shutil.rmtree(cache_dir)
                            except OSError:
                                pass
                else:
                    # ponytail: 仍有 CLI 引用 → 写回保留版本的 entry,cache 不动
                    entry["targets"] = new_targets
                    skill_map[key] = entry
            core.atomic_json_write(core.SKILL_ORIGINS, origins)
        except (OSError, ValueError):
            pass
    invalidate_local_scan()
    invalidate_repo_index()
    return {"ok": True, "removed_links": removed}

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
    Empty `url` clears the entry. Returns the merged origin dict for this item.
    ponytail: 2026-09 — 持 INSTALL_LOCK 防止与并发 install/uninstall 撞 sidecar。"""
    if kind not in ("commands", "agents", "plugins"):
        raise ValueError(f"unsupported kind: {kind!r}")
    if not name or "/" in name and kind != "plugins":
        raise ValueError(f"invalid name: {name!r}")
    if url and not url.startswith("https://github.com/"):
        raise ValueError(f"only github.com urls allowed: {url!r}")
    if not core.acquire_named_lock(core.INSTALL_LOCK, core.INSTALL_LOCK_STALE_S):
        return {"ok": False, "error": "另一个 install/upgrade 正在跑,稍后重试"}
    try:
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

        core.atomic_json_write(core.SKILL_ORIGINS, origins)
        invalidate_local_scan()
        invalidate_repo_index()
        return bucket.get(name, {})
    finally:
        core.release_named_lock(core.INSTALL_LOCK)

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
