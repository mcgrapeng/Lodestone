# -*- coding: utf-8 -*-
"""radar_pkg.serve — HTTP JSON API(组装各域模块;loopback only)。"""
# ponytail: 2026-09 — 把 PROJECT ROOT 加入 sys.path,因为这个文件可能作为
# `python3 radar_pkg/serve.py` 启动(子进程 / /api/restart). 默认 sys.path[0]
# 是脚本所在目录(radar_pkg/),导入 `radar_pkg` 包会失败. 加 path 后无论 cwd 都 OK.
import os as _os_for_path
import sys as _sys_for_path
_PROJECT_ROOT_FROM_INIT = _os_for_path.path.dirname(_os_for_path.path.dirname(_os_for_path.path.abspath(__file__)))
if _PROJECT_ROOT_FROM_INIT not in _sys_for_path.path:
    _sys_for_path.path.insert(0, _PROJECT_ROOT_FROM_INIT)

import datetime
import http.server
import json
import os
import signal as _signal
import socketserver
import subprocess
import sys
import threading
import time
import webbrowser
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from radar_pkg import core, detect
_core_local = core  # ponytail: 2026-09 — /api/local 用 core.start_upgradable_refresh_daemon 等缓存助手
import db  # ponytail: PG 查询(serve 各端点直接使用)
from radar_pkg.crawl import audit, crawl, crawl_lock_held, summarize_lock_held, today


def _pid_alive(pid: int) -> bool:
    """共用:跨平台检测 pid 是否还活着(serve.py cancel 路径 + core.py lock 路径)。"""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # 进程存在,只是当前用户没权限信号
from radar_pkg.core import (
    DATA,
    MANUAL_SEED_REPOS,
    ROOT,
    TOP_5K_LIMIT,
    _repo_slug_from_url,
    is_ai_relevant,
)
from radar_pkg.detect import detect_cli_tools, detect_local_skills, invalidate_local_scan
from radar_pkg.gh import gh_fetch_repo, gh_search
from radar_pkg.install import (
    find_skill_replacements,
    group_capabilities_by_origin,
    install_cli_wrapper,
    install_skill_from_github,
    replace_skill,
    set_capability_origin,
    uninstall_skill,
)
from radar_pkg.match import _annotate_local_installed, _build_plugin_segs, _installed_segments, _load_repo_index

"""radar_pkg.serve — 由 radar.py 搬移(2026-09 架构拆分)。"""
# ponytail: 2026-09 — /api/health 用的进程级启动时间戳(模块加载即设定一次)
_SERVE_STARTED_AT = time.time()


# ponytail: 2026-09 — /yz:ai skill 通过 /api/restart 触发的服务端重启工具。流程:
#   1. 找占住目标端口的进程 PID (lsof -iTCP:port)
#   2. SIGTERM 让它优雅退出; 5s 后还活着就 SIGKILL
#   3. 端口空闲后用 Popen(start_new_session=True) 启动新 serve,日志接到 data/serve.log
#   4. 轮询 /api/health 探活,直到新进程 listen 上为止(最多 10s)
#   5. 返回 {killed_pids, new_pid, port, old_pid} 供 skill 立即重连
# 错误纠正(2026-09 audit v1):此处函数并非死代码 — /api/restart handler (serve.py:892)
# 通过 subprocess('radar.py restart <port>') 调用本函数,这条链是 hot path。原 audit 把
# 它标 dead 是误判,commit 1 误删导致 /api/restart 全部 500。本 commit 恢复。
def _restart_serve(port: int = 8765) -> dict:
    """Restart the radar serve on `port` (default 8765). Safe to call via /api/restart.

    Returns {killed_pids, new_pid, port, old_pid}. Raises on timeout.

    ponytail: 2026-09 — 用 os.fork() 双进程模型.
    当 /api/restart 被调用,父进程(旧 serve)fork 一个子进程后立刻返回 200.
    父进程在 HTTP 响应写完后 os._exit(0). 子进程做实际的 kill + spawn + wait.
    这样子进程不被父进程的死影响(它在父进程 fork 后是独立进程).
    """
    import signal as _signal

    def _pid_using_port(p: int) -> int | None:
        try:
            r = subprocess.run(
                ["lsof", "-nP", f"-iTCP:{p}", "-sTCP:LISTEN", "-t"],
                capture_output=True, text=True, timeout=5,
            )
        except Exception:
            return None
        for line in r.stdout.splitlines():
            line = line.strip()
            if line.isdigit():
                return int(line)
        return None

    def _pids_running_radar_serve() -> list:
        try:
            r = subprocess.run(
                ["pgrep", "-f", "radar.py serve"],
                capture_output=True, text=True, timeout=5,
            )
        except Exception:
            return []
        return [
            int(line.strip())
            for line in r.stdout.splitlines()
            if line.strip().isdigit() and int(line.strip()) != os.getpid()
        ]

    pid = os.fork()
    if pid > 0:
        # Parent: detach from child, return immediately. Child does the work.
        return {
            "killed_pids": [],
            "new_pid": pid,  # the CHILD will spawn the actual new serve
            "port": port,
            "old_pid": _pid_using_port(port),
            "_phase": "forked",
        }

    # === Child process ===
    # Detach so the parent can't accidentally kill us
    os.setsid()

    # 1. Kill old serve
    old_pid = _pid_using_port(port)
    # ponytail: 排除自己 + 父进程 — 我们的子进程 fork 自 OLD serve,
    # kill 自己等于自杀,kill 父进程也会让父进程提前死(响应可能还没 flush).
    # kill 列表应该只有「其他」serve 进程,不包括当前进程树.
    candidates = set(_pids_running_radar_serve() + ([old_pid] if old_pid else []))
    candidates.discard(os.getpid())  # never kill self
    ppid = os.getppid()
    if ppid:
        candidates.discard(ppid)  # never kill direct parent (do_POST thread)
    killed: list = []
    for p in candidates:
        try:
            os.kill(p, _signal.SIGTERM)
            killed.append(p)
        except (ProcessLookupError, PermissionError):
            pass

    # 2. Wait for port to free
    deadline = time.time() + 5.0
    while time.time() < deadline:
        if _pid_using_port(port) is None:
            break
        time.sleep(0.1)
    else:
        for p in candidates:
            try:
                os.kill(p, _signal.SIGKILL)
            except Exception:
                pass
        time.sleep(0.5)
        if _pid_using_port(port) is not None:
            sys.exit(1)

    # 3. Spawn new detached serve
    # ponytail: 关键 — 子进程 fork 后会立刻被 _restart_serve 的 _alive() 等待,
    # 而 _alive() 在子进程内调用, 父进程(即 start_new_session=true 创建的 session)
    # 一旦 sys.exit(0), 整个 session 被 reap, 导致子进程也被收割.
    # 解法: 不在子进程内 _alive() — 把 _alive() 移到另一个独立的临时脚本里执行,
    # 这里只 Popen 后立刻 sys.exit(0), 留 5s 缓冲时间.
    log_fd = os.open(
        DATA / "serve.log",
        os.O_WRONLY | os.O_CREAT | os.O_APPEND,
        0o644,
    )
    # Force synchronous flush — the original serve log uses buffered `print()`,
    # but our f.write() needs explicit flush() to show up before sys.exit below.
    os.write(log_fd, b"")  # noop, just to ensure fd valid
    project_root = str(Path(__file__).parent.parent.resolve())
    with open(DATA / "serve.log", "a") as f:
        f.write(f"[restart] spawning new serve at port {port} (project_root={project_root}, py={sys.executable})\n")
    proc = subprocess.Popen(
        [sys.executable, str(Path(project_root) / "radar.py"), "serve", str(port)],
        cwd=project_root,
        env={**os.environ, "PYTHONPATH": project_root},
        stdout=log_fd,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    os.close(log_fd)
    with open(DATA / "serve.log", "a") as _log:
        _log.write(f"[restart] Popen returned proc.pid={proc.pid}, old killed={killed}\n")
        _log.flush()

    # Give the subprocess a moment to bind
    with open(DATA / "serve.log", "a") as _log:
        _log.write("[restart] before time.sleep(2.0)\n")
        _log.flush()
    time.sleep(2.0)
    with open(DATA / "serve.log", "a") as _log:
        _log.write("[restart] after time.sleep(2.0)\n")
        _log.flush()

    # Quickly verify alive once (best-effort — don't block forever)
    def _alive(p: int) -> bool:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(f"http://127.0.0.1:{p}/api/health", timeout=1) as r:
                return r.status == 200
        except Exception:
            return False

    # ponytail: 不等 alive. 子进程已经 setsid detach, OLD serve 已被 kill,
    # 我们 sys.exit(0) 不会影响它. 这里只 Popen + 立即退出 — 失败的 bind 会在
    # 子进程自己的日志里显式出现,我们不需要在这里确认.
    # ponytail: 2026-09 P4 — 删 dead code。之前 `_alive_check` 函数定义在 sys.exit(0)
    # 之后,永远不会执行(reader 困惑,audit 误判)。`_alive` 也已被此函数下面注释
    # 取代为「不等 alive」,整段删除。
    with open(DATA / "serve.log", "a") as f:
        f.write(f"[restart] spawning done, exiting child (new_pid={proc.pid} port={port})\n")
        f.flush()
    sys.exit(0)


def serve(port=8765):
    """Pure JSON API server — Vite (5173) proxies /api/* here.
    Endpoints:
      GET  /api/data    → {hot_now, categories, fetched_at}
      GET  /api/local   → {skills, commands, agents, plugins, clis, ...}
      GET  /api/top     → paginated 1k+ star AI repos
      GET  /api/gain    → repos with star delta ≥ min_delta (24h / 7d)
      GET  /api/workbuddy → workbuddy picks
      POST /api/crawl   → spawn `radar.py crawl` in background
      POST /api/install → clone+symlink a skill
      POST /api/install-cli → wrap a CLI as slash command
      POST /api/local/origin → tag a command/agent/plugin with GitHub URL
      POST /api/local/replace → replace an installed skill with a stronger one
    """
    socketserver.ThreadingTCPServer.allow_reuse_address = True

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            sys.stderr.write(f"  [{self.command}] {self.path}\n")

        # ponytail: security — this server can clone repos into your skills dirs.
        # Browsers always send Origin on cross-origin POSTs, so a non-local Origin
        # header = another website trying drive-by installs → reject. Local curl /
        # same-origin Vite proxy send none and pass.
        def _origin_forbidden(self) -> bool:
            origin = (self.headers.get("Origin") or "").strip().lower()
            if not origin:
                return False
            # ponytail: 2026-09 P3 修复 — 接受 http + https + 用户自定义 ALLOWED_ORIGINS。
            # 旧实现只允许 http://localhost* — Codespaces / GitHub Pages / 自建域
            # HTTPS 部署全部 403。环境变量 RADAR_ALLOWED_ORIGINS 用逗号分隔覆盖。
            allowed = (
                "http://localhost",
                "http://127.0.0.1",
                "http://[::1]",
                "https://localhost",
                "https://127.0.0.1",
                "https://[::1]",
            )
            extra = os.environ.get("RADAR_ALLOWED_ORIGINS", "")
            if extra:
                allowed = allowed + tuple(o.strip().lower() for o in extra.split(",") if o.strip())
            return not any(origin.startswith(prefix) for prefix in allowed)

        def _json(self, data, status=200, etag=False):
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            tag = None
            if etag:
                # ponytail: 2026-09 — ETag 协商。前端 30s 轮询 /api/data（~600KB/次），
                # 304 让未变化的响应零传输。no-store 阻止浏览器自动缓存，所以由
                # 前端手动带 If-None-Match（见 frontend/src/lib/api.ts）。
                tag = '"' + __import__("hashlib").md5(body).hexdigest()[:16] + '"'
                if (self.headers.get("If-None-Match") or "").strip() == tag:
                    self.send_response(304)
                    self.send_header("ETag", tag)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            if tag:
                self.send_header("ETag", tag)
            self.end_headers()
            self.wfile.write(body)

        def _read_body(self):
            length = int(self.headers.get("Content-Length", 0))
            if not length:
                return {}
            return json.loads(self.rfile.read(length).decode("utf-8"))

        # ponytail: /zp 一键体验 — serve 不再是纯 API：非 /api 的 GET 直接托管
        # frontend/dist 构建产物（前端 BASE='' 同源相对路径，无需 Vite）。
        # 开发模式仍走 `cd frontend && npm run dev`（热更新）。
        _STATIC_TYPES = {
            ".js": "text/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".html": "text/html; charset=utf-8",
            ".svg": "image/svg+xml",
            ".png": "image/png",
            ".ico": "image/x-icon",
            ".woff2": "font/woff2",
        }

        def _serve_static(self):
            root = (ROOT / "frontend" / "dist").resolve()
            if not (root / "index.html").is_file():
                self.send_error(
                    503,
                    "frontend/dist not built — run `cd frontend && npm install && npm run build`",
                )
                return
            path = urllib.parse.urlparse(self.path).path
            # ponytail: 2026-09 — /assets/* 与白名单静态文件(favicon.svg /
            # vite.svg 等)从 dist 直返;其他路径 SPA 兜底回 index.html。旧实现只放行
            # /assets/* → /favicon.svg 被 SPA 兜底吃掉,浏览器 tab 没图标。
            if path.startswith("/assets/") or path in {"/favicon.svg", "/favicon.ico", "/vite.svg"}:
                f = (root / path.lstrip("/")).resolve()
                # ponytail: path-traversal guard — /assets/../radar.py 不许读源码
                if root not in f.parents or not f.is_file():
                    self.send_error(404)
                    return
                body = f.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", self._STATIC_TYPES.get(f.suffix, "application/octet-stream"))
                self.send_header("Content-Length", str(len(body)))
                # ponytail: 文件名带 hash → 内容变名字变，可放心长缓存
                self.send_header("Cache-Control", "public, max-age=86400")
                self.end_headers()
                self.wfile.write(body)
                return
            # SPA 兜底：其余路径（含 /）都回 index.html，路由由前端接管
            body = (root / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            # ponytail: 2026-09 — /api/health 给 /yz:ai skill 用于探测 serve 存活。
            # 返回 {ok, port, pid, uptime_seconds} — skill 据此决定是否要 /api/restart 杀旧进程。
            # ponytail: 2026-09 — 提前 import core。下方 /api/install/status 等新端点
            # 用 core.read_install_status()。原本只有 /api/llm/status 内嵌 `from radar_pkg
            # import core`,在那个 if 分支之后才执行 — 触发 UnboundLocalError。
            from radar_pkg import core as _core_get
            if self.path == "/api/health":
                self._json({
                    "ok": True,
                    "port": self.server.server_address[1],
                    "pid": os.getpid(),
                    "uptime_seconds": round(time.time() - _SERVE_STARTED_AT, 1),
                })
                return
            # ponytail: settings UI 持久化层。无文件返 null + updated_at。
            if self.path == "/api/settings":
                from radar_pkg import settings as _settings
                loaded = _settings.load()
                self._json({
                    "settings": loaded,
                    "updated_at": (loaded or {}).get("updated_at"),
                })
                return
            # ponytail: 2026-09 P3 — /api/llm/status 给前端 Settings 抽屉看
            # 「模型配了没 + 上次生成于何时」。前端轮询此端点显示进度 / 上次结果。
            if self.path == "/api/llm/status":
                from radar_pkg import core, settings as _settings
                status = {}
                if core.LLM_STATUS_PATH.exists():
                    try:
                        status = json.loads(core.LLM_STATUS_PATH.read_text())
                    except Exception:
                        status = {}
                running = summarize_lock_held()
                provider, fields = _settings.active_config()
                # ponytail: 2026-09 — configured 要看 provider 的必填字段真的填了。
                # anthropic/openai 必须有 api_key;ollama 必须有 host。仅 base_url 默认值
                # + 空 api_key 不算「已配」(用户能 save 但跑会失败,前端按钮不该亮)。
                configured = False
                if provider == "anthropic":
                    configured = bool(fields.get("api_key"))
                elif provider == "openai":
                    configured = bool(fields.get("api_key")) and bool(fields.get("base_url"))
                elif provider == "ollama":
                    configured = bool(fields.get("host"))
                # ponytail: 2026-09 — 进度条数据(running + current + total)。
                # 跑批时 analyze_many 每 ~2.5% 写一次 llm_status.json,
                # status dict 里有 current/total/analyzed_running。running 优先看锁,
                # 锁释放但 status 还残留 running=True 时用 updated_at 兜底(5s 内视为跑完)。
                running_effective = running
                current = status.get("current")
                total = status.get("total")
                if running_effective and current is None and total is None:
                    # 没进度数据但锁在 — 启动后第一批还没写盘
                    current = 0
                    total = status.get("total") or 0
                self._json({
                    "configured": configured,
                    "provider": provider or None,
                    "running": running_effective,
                    "current": current,
                    "total": total,
                    "analyzed_running": status.get("analyzed_running"),
                    "started_at": status.get("started_at"),
                    "last_run": status.get("last_run_at"),
                    "last_analyzed": status.get("analyzed"),
                    "last_total": status.get("total"),
                    "last_duration_s": status.get("duration_s"),
                    "last_source": status.get("source"),
                    "last_model": status.get("model"),
                    "updated_at": status.get("updated_at"),
                })
                return
            # ponytail: 2026-09 — /api/crawl/progress 给前端进度条 banner。
            # 解析 data/crawl.log 最近阶段 + 当前 bar；running 走 crawl_lock_held，
            # 不在时返 last_done_at 让前端知道上次成功于何时。
            # ponytail: 2026-09 — /api/install/status 给本机 tab UpgradeProgressBanner。
            # 镜像 /api/llm/status 极简结构(running/current/total/label/started_at/finished_at)。
            if self.path == "/api/install/status":
                self._json(_core_get.read_install_status())
                return
            if self.path == "/api/crawl/progress":
                import re as _re
                log_path = DATA / "crawl.log"
                running = crawl_lock_held()
                phase = None
                label = None
                current = None
                total = None
                pct = None
                eta = None
                last_lines: list[str] = []
                pid = None
                started_at = None
                log_mtime = None
                if log_path.exists():
                    try:
                        st = log_path.stat()
                        log_mtime = st.st_mtime
                        # ponytail: 读尾部 ~64KB — 单次 crawl 总日志 ~15-25KB,
                        # 64KB 覆盖完整最近一个阶段(包括可能跨多页的进度)。
                        with log_path.open("rb") as _f:
                            _f.seek(max(0, st.st_size - 65536))
                            text = _f.read().decode("utf-8", errors="replace")
                        all_lines = [ln for ln in text.splitlines() if ln.strip()]
                        last_lines = all_lines[-15:]
                        # ponytail: 2026-09 — 只在「最近 phase 之后」找 bar。
                        # 之前用 reversed last_lines 找最近 bar → 跨阶段时显示 stale 值
                        # (README 阶段没发 bar,前端就看到上一阶段 100% trending)。
                        phase_idx = None
                        for i in range(len(all_lines) - 1, -1, -1):
                            if _re.match(r"^──\s+.+?\s+──$", all_lines[i].strip()):
                                phase_idx = i
                                break
                        if phase_idx is not None:
                            phase = _re.match(
                                r"^──\s+(.+?)\s+──$", all_lines[phase_idx].strip()
                            ).group(1)
                            # 在 phase 行之后找最近 bar
                            for j in range(len(all_lines) - 1, phase_idx, -1):
                                _bm = _re.search(
                                    r"\[\s*[█░]+\s*\]\s+([\d.]+)%\s+(\d+)/(\d+)\s+(\S+?)(?:\s|$)",
                                    all_lines[j],
                                )
                                if _bm:
                                    pct = float(_bm.group(1))
                                    current = int(_bm.group(2))
                                    total = int(_bm.group(3))
                                    label = _bm.group(4)
                                    break
                            # ETA: phase 之后最近 ✓/done 行
                            for j in range(len(all_lines) - 1, phase_idx, -1):
                                if all_lines[j].strip().startswith("✓") or " done" in all_lines[j]:
                                    _em = _re.search(r"\(\d+s(?:, ~\d+s left)?\)", all_lines[j])
                                    if _em:
                                        eta = _em.group(0)
                                    break
                        # 解析 PID
                        try:
                            pid = int(log_path.with_name("crawl.lock").read_text().strip())
                        except Exception:
                            pid = None
                    except Exception:
                        pass
                # 起始时间 = crawl.lock mtime(若有)
                started_at_ts = None
                lock_path = DATA / "crawl.lock"
                if lock_path.exists():
                    try:
                        started_at_ts = lock_path.stat().st_mtime
                    except Exception:
                        pass
                elapsed_s = round(time.time() - started_at_ts, 1) if started_at_ts else None
                self._json({
                    "running": running,
                    "phase": phase,
                    "label": label,
                    "current": current,
                    "total": total,
                    "pct": pct,
                    "eta": eta,
                    "pid": pid,
                    "started_at": started_at_ts,
                    "elapsed_s": elapsed_s,
                    "log_mtime": log_mtime,
                    "last_lines": last_lines,
                })
                return
            # ponytail: 2026-09 — /api/restart 给 /yz:ai skill 一键重启.
            # 杀掉当前端口的旧 serve 进程,启动新 detached serve,等就绪后返回.
            # 旧进程仍能继续响应本请求(200 返回后自杀).
            # /api/restart handler is in do_POST (state-changing op).
            if self.path == "/api/data":
                if db._DB_OK:
                    try:
                        conn = db.connect()
                        try:
                            hot = db.query_hot_now(conn, limit=40)
                            cats = db.query_categories(conn)
                            # ponytail: 2026-09 P0 修复 — PG 模式此前不返 stars_today/trending,
                            # HeroStats "今日上榜" 永远 0、Trending tab 标题下显示星标榜。
                            # 单查 trending 行,与 JSON 模式对齐两个字段。
                            cur = conn.cursor()
                            cur.execute(
                                "SELECT name, url, description, desc_zh, stars, forks, lang, "
                                "topics, pushed_at, updated_at, trending, first_seen_at, "
                                "stars_today, is_skill, summary_sections_json AS summary_sections, "
                                "analysis_5d_json AS analysis_5d "
                                "FROM repos WHERE is_ai_relevant AND stars_today IS NOT NULL "
                                "ORDER BY stars_today DESC"
                            )
                            trending_rows = [d | {"local_installed": False, "trending": True} for d in db._dicts(cur)]
                            stars_today = {r["name"]: r["stars_today"] for r in trending_rows if r.get("stars_today") is not None}
                        finally:
                            conn.close()
                        # ponytail: per-request annotation — the DB doesn't know what's installed locally
                        local_sk = detect_local_skills()
                        segs = _installed_segments(local_sk)
                        plugin_segs = _build_plugin_segs(local_sk)
                        _annotate_local_installed(hot, segs, plugin_segs)
                        _annotate_local_installed(cats, segs, plugin_segs)
                        _annotate_local_installed(trending_rows, segs, plugin_segs)
                        return self._json(
                            {
                                "hot_now": hot,
                                "categories": cats,
                                "fetched_at": datetime.datetime.now().isoformat(),
                                # 2026-09 P0 — 与 JSON 路径对齐,前端 HeroStats/Trending tab 不再退化
                                "stars_today": stars_today,
                                "trending": trending_rows,
                            },
                            etag=True,
                        )
                    except Exception as e:
                        print(
                            f"  [warn] /api/data db read failed: {e}; falling back to data/latest.json",
                            file=sys.stderr,
                        )
                # ponytail: fallback — read latest.json (PG-unavailable mode or DB transient error)
                latest = DATA / "latest.json"
                if latest.exists():
                    snap = json.loads(latest.read_text())
                    hot = snap.get("hot_now") or []
                    cats = snap.get("categories") or []
                    local_sk = detect_local_skills()
                    segs = _installed_segments(local_sk)
                    plugin_segs = _build_plugin_segs(local_sk)
                    _annotate_local_installed(hot, segs, plugin_segs)
                    _annotate_local_installed(cats, segs, plugin_segs)
                    return self._json(
                        {
                            "hot_now": hot,
                            "categories": cats,
                            "fetched_at": snap.get("fetched_at"),
                            # 视觉审查修复：JSON 回退模式此前丢掉 stars_today，
                            # 前端「今日上榜」永远显示 0（与卡片 +2206 当场矛盾）。
                            "stars_today": snap.get("stars_today") or {},
                            # 2026-09：trending 专区列表（趋势 tab 消费）
                            "trending": snap.get("trending") or [],
                        },
                        etag=True,
                    )
                return self._json(
                    {
                        "hot_now": [],
                        "categories": [],
                        "fetched_at": None,
                        "note": "no data — run ./radar.py crawl",
                    }
                )
            if self.path == "/api/local":
                local = detect_local_skills()
                legacy_clis = detect_cli_tools()
                repos_idx = _load_repo_index()
                replacements = find_skill_replacements(local, repos_idx)
                # ponytail: merge detect_local_skills clis (brew/uv/cargo/cask) with legacy 14 CLI list
                merged_clis = dict(legacy_clis)
                for group, items in (local.get("clis") or {}).items():
                    if not items:
                        continue
                    merged_clis[group] = (
                        items  # e.g. {"brew": [...834 names...], "uv": [...]}
                    )
                # ponytail: 2026-09 — 本机 tab 核心数据。每项 skill 带 status (up_to_date /
                # behind / cache_missing / check_failed / orphan),upgradable 布尔,local/remote SHA。
                # ponytail: 2026-09 — stale-while-revalidate 改造:upgradable 走 5min
                # 缓存,后台 daemon 周期性刷新(serve.py 启动时 start_upgradable_refresh_daemon),
                # /api/local handler 永远秒返(老 cache 也返,后台刷新后下次拿到新的)。
                # 旧实现每个 HTTP 请求都跑 ls-remote — 100 个 skill = 25 min 阻塞线程。
                from radar_pkg.install import compute_upgradable
                skills_data = local["skills"]
                # ponytail: 启动后台 daemon(幂等)。id(skills) 作 key,但 skills_data
                # 是新 dict — 用稳定 key:"local-skills-v1"。daemon 会持续刷整个全局 cache,
                # 但需在第一次 /api/local 调用后才知道有哪些 skill,所以这里 lazy 启动。
                _core_local.start_upgradable_refresh_daemon()
                upgradable_map = _core_local.read_upgradable_cache_or_none()
                # ponytail: 2026-09 P1 修复 — 缓存 miss 时只算缺失子集,不再全量重算。
                # 旧实现 cache_stale=True 就跑全量 compute_upgradable → 100 skill × 15s
                # = 25 min 阻塞 HTTP 线程;同时与 daemon 竞争触发 GitHub 60/hr 限流。
                # 现在:cache 完全空 → 不阻塞(让 daemon 首次填),返回空 dict(UI 显示"未检查")。
                #      cache 存在但缺 N 个 → 只算这 N 个,daemon 5min 内填全。
                if upgradable_map is None:
                    upgradable_map = {}  # daemon 5min 内首次填充;UI 显示 dashed "未检查"
                else:
                    missing = [n for n in skills_data if n not in upgradable_map]
                    if missing:
                        try:
                            fresh = compute_upgradable(
                                {n: skills_data[n] for n in missing}
                            )
                            upgradable_map = {**upgradable_map, **fresh}
                            _core_local.write_upgradable_cache(upgradable_map)
                        except Exception:
                            pass
                # ponytail: 把 status + sha 注入到每个 skill 节点
                for name, info in skills_data.items():
                    if name in upgradable_map:
                        u = upgradable_map[name]
                        info["upgradable"] = bool(u.get("upgradable"))
                        info["upgrade_reason"] = u.get("reason")
                        info["local_sha"] = u.get("local_sha")
                        info["remote_sha"] = u.get("remote_sha")
                upgradable_count = sum(
                    1 for name, v in upgradable_map.items()
                    if name in skills_data and v.get("upgradable")
                )
                return self._json(
                    {
                        "skills": skills_data,
                        "commands": local["commands"],
                        "agents": local["agents"],
                        "plugins": local["plugins"],
                        "clis": merged_clis,
                        "mcp_servers": local.get("mcp_servers") or [],
                        "groups": group_capabilities_by_origin(local),
                        "replacements": replacements,
                        "upgradable": upgradable_map,
                        "counts": {
                            "skills": len(skills_data),
                            "commands": len(local["commands"]),
                            "agents": len(local["agents"]),
                            "plugins": len(local["plugins"]),
                            "clis": sum(
                                len(v) if isinstance(v, list) else 1
                                for v in merged_clis.values()
                            ),
                            "mcp_servers": len(local.get("mcp_servers") or []),
                            "upgradable": upgradable_count,
                        },
                        "total": (
                            len(skills_data)
                            + len(local["commands"])
                            + len(local["agents"])
                            + len(local["plugins"])
                            + sum(
                                len(v) if isinstance(v, list) else 1
                                for v in merged_clis.values()
                            )
                            + len(local.get("mcp_servers") or [])
                        ),
                        # ponytail: 2026-09 — cache 元信息,给前端 banner 用(exists / age_s /
                        # total / computing)。"未检查"徽章的"未"是因为 cache 没算,
                        # banner 应该显示这个原因而不是 292 个相同徽章。
                        "cache_state": {
                            **_core_local.read_upgradable_cache_meta(),
                            "computing": bool(_core_local.read_refresh_status().get("computing")),
                            "last_trigger_at": _core_local.read_refresh_status().get("started_at"),
                            # ponytail: 2026-09 — error 字段(compute 失败 / 已取消)也透出。
                            # 前端 banner 否则会一直显示"在算",但 status 实际已终态。
                            "error": _core_local.read_refresh_status().get("error"),
                        },
                    }
                )
            # ponytail: 2026-09 — 手动触发 upgradable 重算。
            # POST 触发后台线程(立即返 200,不阻塞),GET 轮询状态。
            # (POST handler 实现在 do_POST 里;这里 do_GET 只返 status)
            if self.path == "/api/local/refresh/status":
                self._json({
                    **_core_local.read_refresh_status(),
                    "cache": _core_local.read_upgradable_cache_meta(),
                })
                return
            # ponytail: 2026-09 — 手动触发 upgradable 重算。前端首次进 tab 或用户点
            # "立即重新计算"按钮时调。后台 fork 线程跑(立即返 200,不阻塞 HTTP),
            # 跑完写 cache + 清 computing 标志。前端轮询 /api/local/refresh/status 看进度。
            # (实现在 do_POST 里; GET 这里只返 /refresh/status 状态)
            if self.path == "/api/local/refresh/status":
                self._json({
                    **_core_local.read_refresh_status(),
                    "cache": _core_local.read_upgradable_cache_meta(),
                })
                return
            # ponytail: /api/stats — lightweight digest for the 📊 RTK-style token economy
            # panel + ecosystem breakdown. Computed from PG (or JSON snapshot fallback).
            if self.path == "/api/stats":
                try:
                    stats = {"by_lang": {}, "by_topic": {}, "total_repos": 0, "total_stars": 0}
                    pg_failed = False
                    # ponytail: 2026-08 — language allowlist. The repo `lang`
                    # field can hold non-language tags leaked from upstream
                    # sources ("Transformers", "Mcp server", "Model" — these
                    # are HF library_name / registry pseudo-langs, not programming
                    # languages). Filter to a curated set so by_lang counts
                    # programming languages only.
                    LANG_ALLOWLIST = {
                        "Python", "JavaScript", "TypeScript", "Java", "C++", "C",
                        "C#", "Go", "Rust", "Ruby", "PHP", "Swift", "Kotlin",
                        "Scala", "Shell", "HTML", "CSS", "Lua", "Dart", "Elixir",
                        "Haskell", "OCaml", "R", "Julia", "Racket", "Erlang",
                        "Groovy", "Perl", "Nim", "Crystal", "Zig", "V", "Odin",
                        "Vue", "Svelte", "CoffeeScript", "Hack",
                        "F#", "Clojure", "Common Lisp", "Emacs Lisp", "Scheme",
                        "Tcl", "Vala", "Verilog", "VHDL", "Solidity", "Move",
                        "Dockerfile", "Makefile",
                        "Markdown", "HTML+ERB", "PLpgSQL",
                    }
                    if db._DB_OK:
                        try:
                            conn = db.connect()
                            try:
                                cur = conn.cursor()
                                cur.execute(
                                    "SELECT lang, COUNT(*), SUM(stars) FROM repos "
                                    "WHERE is_ai_relevant AND lang IS NOT NULL "
                                    "AND lang = ANY(%s) "
                                    "GROUP BY lang",
                                    (list(LANG_ALLOWLIST),),
                                )
                                for row in cur.fetchall():
                                    stats["by_lang"][row[0]] = {"count": row[1], "stars": int(row[2] or 0)}
                                cur.execute("SELECT t, COUNT(*) FROM (SELECT unnest(topics) AS t FROM repos WHERE is_ai_relevant) x GROUP BY t ORDER BY COUNT(*) DESC LIMIT 20")
                                for row in cur.fetchall():
                                    stats["by_topic"][row[0]] = row[1]
                                cur.execute("SELECT COUNT(*), SUM(stars) FROM repos WHERE is_ai_relevant")
                                row = cur.fetchone()
                                stats["total_repos"] = row[0]
                                stats["total_stars"] = int(row[1] or 0)
                            finally:
                                conn.close()
                        except Exception as e:
                            # 2026-08 — PG installed but unreachable. Fall through to
                            # JSON snapshot path so /api/stats doesn't return empty
                            # when the credentials are wrong / DB is down.
                            pg_failed = True
                            stats["db_error"] = str(e)
                    if (not db._DB_OK) or pg_failed:
                        # ponytail: JSON fallback (no PG OR PG failed)
                        latest = DATA / "latest.json"
                        if latest.exists():
                            snap = json.loads(latest.read_text())
                            counts: dict[str, int] = {}
                            for cat in snap.get("categories", []):
                                for x in cat.get("repos", []):
                                    # normalize lang casing — 'Python' and 'python' should merge
                                    raw = (x.get("lang") or "—").strip()
                                    key = raw if raw == "—" else raw[:1].upper() + raw[1:].lower()
                                    # 2026-08 — filter to programming languages only;
                                    # upstream tags like "Transformers", "Mcp server"
                                    # would otherwise show in by_lang. Compare case-
                                    # insensitively since the allowlist uses Title Case
                                    # but data may come in any case.
                                    if key != "—" and key not in LANG_ALLOWLIST and key.lower() not in {l.lower() for l in LANG_ALLOWLIST}:
                                        continue
                                    counts[key] = counts.get(key, 0) + 1
                            # sort by count desc, keep top 15
                            sorted_langs = sorted(counts.items(), key=lambda x: -x[1])[:15]
                            stats["by_lang"] = {k: {"count": v, "stars": 0} for k, v in sorted_langs}
                            # ponytail: same dedup logic for topics — lowercase normalize
                            topic_counts: dict[str, int] = {}
                            for cat in snap.get("categories", []):
                                for x in cat.get("repos", []):
                                    for t in (x.get("topics") or []):
                                        tk = t.strip().lower()
                                        if tk:
                                            topic_counts[tk] = topic_counts.get(tk, 0) + 1
                            sorted_topics = sorted(topic_counts.items(), key=lambda x: -x[1])[:30]
                            stats["by_topic"] = {k: v for k, v in sorted_topics}
                            stats["total_repos"] = snap.get("total_unique", 0)
                            stats["total_stars"] = sum(r.get("stars", 0) for r in snap.get("hot_now", []))
                            if pg_failed:
                                stats["note"] = "PG unreachable — showing JSON snapshot"
                    self._json(stats)
                except Exception as e:
                    self._json({"error": str(e)}, status=500)
                return

            if self.path == "/api/scrapers/status":
                # ponytail: exposes the {engine: available} map for the 🛠 引擎
                # panel in the UI. Cached via scrapers.status() which itself caches
                # the underlying is_available() calls.
                try:
                    from scrapers import status as _scraper_status

                    self._json(_scraper_status())
                except ImportError:
                    self._json({"error": "scrapers module unavailable"}, status=503)
                return
            if self.path == "/api/workbuddy":
                picks_path = DATA / "workbuddy_picks.json"
                picks = []
                if picks_path.exists():
                    try:
                        picks = json.loads(picks_path.read_text())
                    except (OSError, ValueError):
                        picks = []
                return self._json({"picks": picks, "count": len(picks)})
            if self.path.startswith("/api/top"):
                # ponytail: server-paginate from PG (was: read latest.json + slice client-side)
                parsed = urllib.parse.urlparse(self.path)
                qs = urllib.parse.parse_qs(parsed.query)
                try:
                    page = max(1, int(qs.get("page", ["1"])[0]))
                except ValueError:
                    page = 1
                try:
                    size = min(48, max(1, int(qs.get("size", ["12"])[0])))
                except ValueError:
                    size = 12
                sort = qs.get("sort", ["stars"])[0]
                if db._DB_OK:
                    try:
                        conn = db.connect()
                        try:
                            data = db.query_top_5k(
                                conn, page=page, size=size, sort=sort
                            )
                        finally:
                            conn.close()
                        local_sk = detect_local_skills()
                        _annotate_local_installed(
                            data.get("repos"),
                            _installed_segments(local_sk),
                            _build_plugin_segs(local_sk),
                        )
                        return self._json(data)
                    except Exception as e:
                        print(
                            f"  [warn] /api/top db read failed: {e}; falling back to latest.json",
                            file=sys.stderr,
                        )
                # ponytail: fallback — paginate all repos from latest.json in-memory.
                # Filter to 1k+ stars to mirror PG query_top_5k's star gate so the
                # JSON-only mode doesn't show 50-star repos in the "1k+ 主流" view.
                latest = DATA / "latest.json"
                if latest.exists():
                    snap = json.loads(latest.read_text())
                    all_repos = list(snap.get("hot_now") or []) + [
                        r
                        for c in (snap.get("categories") or [])
                        for r in c.get("repos") or []
                    ]
                    # dedupe by name, keep highest stars
                    by_name = {}
                    for r in all_repos:
                        n = r.get("name")
                        if not n:
                            continue
                        if n not in by_name or r.get("stars", 0) > by_name[n].get(
                            "stars", 0
                        ):
                            by_name[n] = r
                    # 2026-08 — drop the ≥1000 ⭐ filter. The "1k+ 主流 AI 项目"
                    # view should show ALL mainstream AI tools / skills / plugins
                    # regardless of star count (a fresh trending MCP server with
                    # 200 stars is still mainstream). The category filter at the
                    # front-end side is the right way to gate; the API should
                    # return the full pool.
                    repos_1k = list(by_name.values())
                    # ponytail: pin MANUAL_SEED_REPOS to the front so they show up regardless of stars rank
                    # (lidge-jun/opencodex = 3264⭐ is in MANUAL_SEED but doesn't make top 48 by stars)
                    seen = set(r["name"] for r in repos_1k)
                    pinned_first = []
                    for full_name in MANUAL_SEED_REPOS:
                        if full_name in seen:
                            pinned_first.append(by_name[full_name])
                            seen.discard(full_name)
                    rest = [r for r in repos_1k if r["name"] in seen]
                    if sort == "stars":
                        sort_key = lambda r: r.get("stars", 0)
                        reverse = True
                    elif sort == "recent":
                        sort_key = lambda r: r.get("pushed", "") or ""
                        reverse = True
                    elif sort == "name":
                        sort_key = lambda r: (r.get("name") or "").lower()
                        reverse = False
                    else:
                        sort_key = lambda r: r.get("stars", 0)
                        reverse = True
                    repos = pinned_first + sorted(rest, key=sort_key, reverse=reverse)
                    total = len(repos)
                    start = (page - 1) * size
                    page_repos = repos[start : start + size]
                    local_sk = detect_local_skills()
                    _annotate_local_installed(
                        page_repos,
                        _installed_segments(local_sk),
                        _build_plugin_segs(local_sk),
                    )
                    return self._json(
                        {
                            "repos": page_repos,
                            "total": total,
                            "page": page,
                            "size": size,
                            "pages": max(1, (total + size - 1) // size),
                        }
                    )
                return self._json(
                    {"error": "no data — run ./radar.py crawl"}, status=503
                )
            if self.path.startswith("/api/gain"):
                parsed = urllib.parse.urlparse(self.path)
                qs = urllib.parse.parse_qs(parsed.query)
                try:
                    min_delta = min(10000, max(0, int(qs.get("min_delta", ["100"])[0])))
                except ValueError:
                    min_delta = 100
                try:
                    page = max(1, int(qs.get("page", ["1"])[0]))
                except ValueError:
                    page = 1
                try:
                    size = min(48, max(1, int(qs.get("size", ["24"])[0])))
                except ValueError:
                    size = 24
                # ponytail: only 24h window — data source is repos.stars_today (from github.com/trending)
                # ponytail: 26h/44h (was 20h/4h) — the original 4h recent window never captured
                # a daily-crawl row (crawls are 24h apart), so the snapshot_gain CTE was always
                # empty. 26h gives us "today's snapshot", 44h gives us "yesterday's snapshot" —
                # this works for any cadence from 2×/day to once/2days.
                prev_ago, recent_ago = "44 hours", "26 hours"
                if db._DB_OK:
                    try:
                        conn = db.connect()
                        try:
                            data = db.query_gain(
                                conn,
                                prev_ago=prev_ago,
                                recent_ago=recent_ago,
                                min_delta=min_delta,
                                page=page,
                                size=size,
                            )
                        finally:
                            conn.close()
                        local_sk = detect_local_skills()
                        _annotate_local_installed(
                            data.get("gainers"),
                            _installed_segments(local_sk),
                            _build_plugin_segs(local_sk),
                        )
                        data["range"] = "24h"
                        # ponytail: cold start — gain needs consecutive daily crawls (stars_today
                        # from trending + ≥20h of snapshots). Tell the user instead of an empty tab.
                        if not data.get("gainers"):
                            data["note"] = (
                                "暂无 24h 增长数据：需连续多天定时 crawl 积累 stars 快照，或当日 GitHub trending 页无 AI 项目。"
                            )
                        return self._json(data)
                    except Exception as e:
                        print(
                            f"  [warn] /api/gain db read failed: {e}; falling back to latest.json",
                            file=sys.stderr,
                        )
                # ponytail: fallback — compute gainers from latest.json stars_today.
                # Primary source: the top-level `stars_today` map (carried over from trending
                # scrape; populated even when category repos don't carry the field).
                # Secondary source: any per-repo `stars_today` on hot_now / category entries.
                # Tertiary fallback: recent_activity (pushed_at <7d proxy) so the tab is
                # never empty when there's at least fresh data.
                latest = DATA / "latest.json"
                if latest.exists():
                    snap = json.loads(latest.read_text())
                    today_map = dict(snap.get("stars_today") or {})
                    all_repos = list(snap.get("hot_now") or []) + [
                        r
                        for c in (snap.get("categories") or [])
                        for r in c.get("repos") or []
                    ]
                    # ponytail: index all repos by name so we can backfill desc/topics/etc
                    # for the trending repos that are only in today_map (not in any category).
                    by_name: dict = {}
                    for r in all_repos:
                        n = r.get("name")
                        if not n:
                            continue
                        if n not in by_name or r.get("stars", 0) > by_name[n].get(
                            "stars", 0
                        ):
                            by_name[n] = r
                    # ponytail: build gainers — every name with a positive stars_today wins.
                    gainers = []
                    for n, st in today_map.items():
                        if st <= 0:
                            continue
                        rec = by_name.get(n) or {
                            "name": n,
                            "stars": 0,
                            "topics": [],
                            "description": "",
                            "desc_zh": "",
                            "lang": "—",
                        }
                        gainers.append(
                            {
                                **rec,
                                "stars_today": st,
                                "delta_24h": st,
                                "source": "json_snapshot",
                            }
                        )
                    # ponytail: rank by delta desc, filter to AI-relevant / has topics.
                    # Fallback to recent_activity if today_map is empty.
                    if not gainers:
                        cutoff = (
                            datetime.date.today() - datetime.timedelta(days=7)
                        ).isoformat()
                        for r in all_repos:
                            pushed = r.get("pushed", "")
                            if pushed and pushed[:10] >= cutoff:
                                rec = dict(r)
                                rec["recent_activity"] = r.get("stars", 0)
                                gainers.append(rec)
                        if not gainers:
                            return self._json(
                                {
                                    "gainers": [],
                                    "total": 0,
                                    "page": page,
                                    "size": size,
                                    "pages": 1,
                                    "range": "24h",
                                    "note": "stars_today 与 recent_active 都缺失. 跑 `radar.py crawl` 补回.",
                                    "action": "crawl",
                                }
                            )
                    # ponytail: rank by delta desc, paginate, annotate local-installed
                    gainers.sort(
                        key=lambda r: -(
                            (r.get("delta_24h") or 0) + (r.get("recent_activity") or 0)
                        )
                    )
                    total = len(gainers)
                    start = (page - 1) * size
                    page_gainers = gainers[start : start + size]
                    local_sk = detect_local_skills()
                    _annotate_local_installed(
                        page_gainers,
                        _installed_segments(local_sk),
                        _build_plugin_segs(local_sk),
                    )
                    return self._json(
                        {
                            "gainers": page_gainers,
                            "total": total,
                            "page": page,
                            "size": size,
                            "pages": max(1, (total + size - 1) // size),
                            "range": "24h",
                            "note": None,
                        }
                    )
                return self._json(
                    {"error": "no data — run ./radar.py crawl"}, status=503
                )

            # ponytail: code-graph endpoints — integrate graphify + code-review-graph
            # for installed skills so the UI can render rich relationship visualizations.
            if self.path.startswith("/api/graph/"):
                try:
                    slug = urllib.parse.unquote(
                        self.path[len("/api/graph/") :]
                    ).strip("/")
                    owner_repo = slug
                    if "/" not in owner_repo:
                        idx = _load_repo_index()
                        if slug in idx:
                            owner_repo = idx[slug].get("name", "")
                    if "/" not in owner_repo:
                        # ponytail: fall back to local scan — installed skills without
                        # a PG entry should still be resolvable for graph viz.
                        local = detect_local_skills()
                        for s, meta in (local.get("skills") or {}).items():
                            if s == slug:
                                if meta.get("url"):
                                    owner_repo = _repo_slug_from_url(meta["url"])
                                else:
                                    owner_repo = f"local/{slug}"
                                break
                    if "/" not in owner_repo:
                        return self._json(
                            {"error": f"unknown skill: {slug}"}, status=404
                        )
                    owner, repo = owner_repo.split("/", 1)
                    candidates = [
                        core.SKILLS_CACHE / f"{owner}__{repo}",
                        core.SKILLS_CACHE / repo,
                        Path.home() / ".claude" / "skills" / repo,
                        Path.home() / ".codex" / "skills" / repo,
                    ]
                    skill_dir = next(
                        (p for p in candidates if p.exists()), None
                    )
                    if not skill_dir:
                        return self._json(
                            {"error": f"skill {owner_repo} not installed locally"},
                            status=404,
                        )
                    graph_path = skill_dir / "graphify-out" / "graph.json"
                    # ponytail: graceful path — if no graph.json exists, try building it
                    # in-place via `graphify update <skill_dir>` (uses tree-sitter, no LLM).
                    # If still nothing (e.g. SKILL.md-only skills), return an actionable 200.
                    if not graph_path.exists():
                        build = subprocess.run(
                            ["graphify", "update", str(skill_dir), "--no-cluster"],
                            capture_output=True,
                            text=True,
                            timeout=60,
                        )
                        # build.returncode may be 0 even when no code was found
                    if graph_path.exists():
                        r = subprocess.run(
                            [
                                "graphify",
                                "explain",
                                slug,
                                "--graph",
                                str(graph_path),
                            ],
                            capture_output=True,
                            text=True,
                            timeout=30,
                        )
                        if r.returncode == 0:
                            return self._json(
                                {
                                    "ok": True,
                                    "skill": owner_repo,
                                    "source": "graphify",
                                    "explanation": r.stdout.strip(),
                                }
                            )
                    # ponytail: fallback — return install metadata so the UI can still
                    # render *something* useful (stars, topics, readme hint) when the
                    # skill has no code to graph (most Claude Code skills are SKILL.md only).
                    idx = _load_repo_index()
                    repo_meta = idx.get(slug) or {}
                    return self._json(
                        {
                            "ok": True,
                            "skill": owner_repo,
                            "source": "metadata",
                            "explanation": (
                                "此 skill 主要由 SKILL.md 组成（无 Python/TS 代码可做图谱分析）。"
                                "可用的元数据："
                                + (
                                    f"\n  • 描述：{repo_meta.get('description', '')[:160]}"
                                    if repo_meta.get("description")
                                    else ""
                                )
                                + (
                                    f"\n  • ⭐ {repo_meta.get('stars', 0):,}"
                                    if repo_meta.get("stars")
                                    else ""
                                )
                                + (
                                    f"\n  • Topics: {', '.join(repo_meta.get('topics') or [])[:120]}"
                                    if repo_meta.get("topics")
                                    else ""
                                )
                                + (
                                    f"\n  • URL: {repo_meta.get('url')}"
                                    if repo_meta.get("url")
                                    else ""
                                )
                            ).strip(),
                            "repo": repo_meta,
                        }
                    )
                except subprocess.TimeoutExpired:
                    return self._json({"error": "graphify timeout"}, status=504)
                except Exception as e:
                    return self._json({"error": str(e)}, status=500)

            if self.path.startswith("/api/crg/"):
                try:
                    slug = urllib.parse.unquote(
                        self.path[len("/api/crg/") :]
                    ).strip("/")
                    owner_repo = slug
                    if "/" not in owner_repo:
                        idx = _load_repo_index()
                        if slug in idx:
                            owner_repo = idx[slug].get("name", "")
                    if "/" not in owner_repo:
                        local = detect_local_skills()
                        for s, meta in (local.get("skills") or {}).items():
                            if s == slug:
                                if meta.get("url"):
                                    owner_repo = _repo_slug_from_url(meta["url"])
                                else:
                                    owner_repo = f"local/{slug}"
                                break
                    if "/" not in owner_repo:
                        return self._json(
                            {"error": f"unknown skill: {slug}"}, status=404
                        )
                    owner, repo = owner_repo.split("/", 1)
                    candidates = [
                        core.SKILLS_CACHE / f"{owner}__{repo}",
                        core.SKILLS_CACHE / repo,
                        Path.home() / ".claude" / "skills" / repo,
                        Path.home() / ".codex" / "skills" / repo,
                    ]
                    skill_dir = next(
                        (p for p in candidates if p.exists()), None
                    )
                    if not skill_dir:
                        return self._json(
                            {"error": f"skill {owner_repo} not installed locally"},
                            status=404,
                        )
                    r = subprocess.run(
                        ["code-review-graph", "status"],
                        cwd=str(skill_dir),
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    if r.returncode == 0 and r.stdout.strip():
                        return self._json(
                            {
                                "ok": True,
                                "skill": owner_repo,
                                "source": "crg",
                                "stats": r.stdout.strip(),
                            }
                        )
                    # ponytail: graceful — CRG needs a built graph; if status fails (no
                    # graph yet), suggest the build step in the response.
                    return self._json(
                        {
                            "ok": True,
                            "skill": owner_repo,
                            "source": "metadata",
                            "stats": "",
                            "note": (
                                "此 skill 尚未建立 CRG 图谱。运行 "
                                f"`cd {skill_dir} && code-review-graph build` 后重试。"
                                if r.stderr
                                else ""
                            ),
                            "warnings": r.stderr.strip()[:300] if r.stderr else "",
                        }
                    )
                except subprocess.TimeoutExpired:
                    return self._json({"error": "crg timeout"}, status=504)
                except Exception as e:
                    return self._json({"error": str(e)}, status=500)

            # ponytail: 非 /api 的 GET → 托管 frontend/dist（`radar.py web` 一键开浏览器即用）
            self._serve_static()

        def do_POST(self):
            if self._origin_forbidden():
                self._json({"ok": False, "error": "forbidden origin"}, status=403)
                return
            if self.path == "/api/settings":
                # ponytail: 保存 LLM 设置。仅白名单字段落盘（防注入），
                # provider 必须在 3 个允许值内。
                try:
                    body = self._read_body()
                    from radar_pkg import settings as _settings
                    provider = body.get("provider", "")
                    if provider not in _settings._VALID_PROVIDERS:
                        self._json({"ok": False, "error": f"provider must be one of {sorted(_settings._VALID_PROVIDERS)}"}, status=400)
                        return
                    # ponytail: deviation from brief — brief's implementation code only
                    # validates provider and lets settings.save silently filter unknown
                    # keys, but test_post_rejects_unknown_field expects 400 on unknown key.
                    # Loud reject > silent filter: caller gets a clear error, no surprise.
                    unknown = set(body.keys()) - _settings._KEYS
                    if unknown:
                        self._json({"ok": False, "error": f"unknown fields: {sorted(unknown)}"}, status=400)
                        return
                    _settings.save(body)
                    self._json({"ok": True})
                except Exception as e:
                    self._json({"ok": False, "error": str(e)}, status=500)
                return
            if self.path == "/api/llm/test":
                # ponytail: 用前端提供的 provider + fields 临时测一次。
                # 不持久化，只为「连通性 + 模型存在」反馈。
                # SSRF note: 接受任意 URL, threat model 是 loopback-only serve。
                try:
                    body = self._read_body()
                    from radar_pkg import settings as _settings
                    provider = body.get("provider", "")
                    if provider not in _settings._VALID_PROVIDERS:
                        self._json({"ok": False, "error": f"provider must be one of {sorted(_settings._VALID_PROVIDERS)}"}, status=400)
                        return
                    fields = body.get(provider, {})
                    # Build minimal test request per provider
                    if provider == "anthropic":
                        if not fields.get("api_key"):
                            self._json({"ok": False, "error": "anthropic.api_key required"}); return
                        payload = {"model": fields.get("model", "claude-3-5-haiku-latest"), "max_tokens": 5, "messages": [{"role": "user", "content": "hi"}]}
                        req = urllib.request.Request(
                            "https://api.anthropic.com/v1/messages",
                            data=json.dumps(payload).encode(),
                            headers={"x-api-key": fields["api_key"], "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
                            method="POST",
                        )
                    elif provider == "openai":
                        if not fields.get("api_key"):
                            self._json({"ok": False, "error": "openai.api_key required"}); return
                        base = (fields.get("base_url") or "https://api.openai.com/v1").rstrip("/")
                        payload = {"model": fields.get("model", "gpt-4o-mini"), "max_tokens": 5, "messages": [{"role": "user", "content": "hi"}]}
                        req = urllib.request.Request(
                            # ponytail: 2026-09 — base already includes /v1 (industry convention;
                            # OpenAI SDK + Together + Groq all use form ".../v1"). No extra /v1 here.
                            f"{base}/chat/completions",
                            data=json.dumps(payload).encode(),
                            headers={"Authorization": f"Bearer {fields['api_key']}", "Content-Type": "application/json"},
                            method="POST",
                        )
                    else:  # ollama
                        host = (fields.get("host") or "http://127.0.0.1:11434").rstrip("/")
                        req = urllib.request.Request(f"{host}/api/tags", method="GET")
                    try:
                        with urllib.request.urlopen(req, timeout=10) as resp:
                            if resp.status >= 400:
                                self._json({"ok": False, "error": f"upstream {resp.status}"})
                                return
                            body_text = resp.read()
                            # Try to extract model from response (best-effort)
                            model = fields.get("model", "")
                            try:
                                parsed = json.loads(body_text)
                                if provider == "openai":
                                    model = (parsed.get("model") or model)
                                elif provider == "anthropic":
                                    model = parsed.get("model", model) or model
                                # ollama: tags response doesn't echo a single model — keep as-is
                            except Exception:
                                pass
                            self._json({"ok": True, "model": model})
                    except urllib.error.HTTPError as e:
                        # Upstream 4xx/5xx — return as {ok: false, error}, not 500
                        body_text = e.read().decode("utf-8", errors="replace")[:200]
                        self._json({"ok": False, "error": f"upstream {e.code}: {body_text}"})
                    except Exception as e:
                        self._json({"ok": False, "error": str(e)})
                except Exception as e:
                    self._json({"ok": False, "error": str(e)}, status=500)
                return
            # ponytail: 2026-09 — /api/restart 给 /yz:ai skill 一键重启.
            # 设计: spawn 一个完全独立的 `radar.py restart <port>` 子进程(独立 CLI 命令,
            # 不 fork 自当前 serve 进程), 它独立 kill 旧 + spawn 新. 我们 spawn 后立刻
            # 返回 {"status": "restarting"}. 子进程完成 kill → 新 serve 启动.
            if self.path == "/api/restart":
                try:
                    port = 8765
                    # Allow ?port=N override
                    from urllib.parse import urlparse as _up
                    q = _up(self.path).query
                    if "port=" in q:
                        try:
                            port = int(q.split("port=")[1].split("&")[0])
                        except Exception:
                            pass
                    log_fd = os.open(
                        DATA / "restart.log",
                        os.O_WRONLY | os.O_CREAT | os.O_APPEND,
                        0o644,
                    )
                    project_root = str(Path(__file__).parent.parent.resolve())
                    subprocess.Popen(
                        [
                            sys.executable,
                            str(Path(project_root) / "radar.py"),
                            "restart",
                            str(port),
                        ],
                        cwd=project_root,
                        env={**os.environ, "PYTHONPATH": project_root},
                        stdout=log_fd,
                        stderr=subprocess.STDOUT,
                        start_new_session=True,
                        close_fds=True,
                    )
                    os.close(log_fd)
                    # ponytail: 2026-09 P3 修复 — 重启子进程会 kill 父 serve。
                    # 父进程必须在子进程 kill 自己之前把 HTTP response 完整 flush 到 socket,
                    # 否则客户端拿 connection reset。BaseHTTPRequestHandler 不自动 flush,
                    # 这里显式 flush + shutdown write-half。
                    self._json({"ok": True, "status": "restarting", "port": port})
                    try:
                        self.wfile.flush()
                    except Exception:
                        pass
                    try:
                        # shutdown(1) = 关闭 socket 的写半边,客户端能干净 EOF。
                        # 关之前服务端仍能 continue serving 片刻(已被子进程在 5s 内 SIGTERM)。
                        self.connection.shutdown(1)
                    except Exception:
                        pass
                except Exception as e:
                    self._json({"ok": False, "error": str(e)}, status=500)
                return
            # ponytail: 2026-09 — /api/save_summary_batch 给 /yz:ai skill 一次性写入多张卡的
            # 5 桶摘要(items 数组). 模型分批生成 → 一次 POST 提交,后端原子写 cache+snapshot.
            if self.path == "/api/save_summary_batch":
                try:
                    body = self._read_body()
                    items = body.get("items") or []
                    if not isinstance(items, list) or not items:
                        raise ValueError("items must be a non-empty list")
                    cache_path = core.README_ZH_CACHE
                    snap_path = DATA / "latest.json"
                    cache = {}
                    if cache_path.exists():
                        try:
                            cache = json.loads(cache_path.read_text())
                        except Exception:
                            cache = {}
                    snap = json.loads(snap_path.read_text()) if snap_path.exists() else {}
                    snap_index: dict = {}
                    for r in snap.get("hot_now", []) or []:
                        snap_index[r.get("name", "").lower()] = r
                    for c in snap.get("categories", []) or []:
                        for r in c.get("repos", []) or []:
                            snap_index.setdefault(r.get("name", "").lower(), r)
                    for r in snap.get("trending", []) or []:
                        snap_index.setdefault(r.get("name", "").lower(), r)
                    now = time.strftime("%Y-%m-%dT%H:%M:%S")
                    filled = []
                    for item in items:
                        name = (item.get("name") or "").strip()
                        if not name or "/" not in name:
                            continue
                        sections = item.get("sections") or {}
                        clean = {
                            "intro": str(sections.get("intro") or "").strip()[:600],
                            "can_do": str(sections.get("can_do") or "").strip()[:600],
                            "problem": str(sections.get("problem") or "").strip()[:600],
                            "competitive": str(sections.get("competitive") or "").strip()[:600],
                            "when_to_use": str(sections.get("when_to_use") or "").strip()[:600],
                        }
                        key = name.lower()
                        entry = cache.get(key) or {"text": "", "sections": {}}
                        entry["sections"] = {**entry.get("sections", {}), **clean}
                        entry["analysis_5d"] = {
                            "what": clean["intro"],
                            "can_do": clean["can_do"],
                            "problem": clean["problem"],
                            "alternatives": (
                                [{"name": clean["competitive"], "pros": "", "cons": ""}]
                                if clean["competitive"] else []
                            ),
                            "when_to_use": clean["when_to_use"],
                        }
                        entry["_analysis_5d_source"] = "skill_model"
                        entry["_analysis_5d_at"] = now
                        cache[key] = entry
                        repo_snap = snap_index.get(key)
                        if repo_snap is not None:
                            repo_snap["summary_sections"] = {**repo_snap.get("summary_sections", {}), **clean}
                            repo_snap["analysis_5d"] = entry["analysis_5d"]
                        filled.append({"name": name, "buckets": sum(1 for v in clean.values() if v)})
                    # ponytail: 原子写(tmp + rename)避免并发 worker lost update
                    tmp_c = cache_path.with_suffix(".json.tmp")
                    tmp_c.write_text(json.dumps(cache, ensure_ascii=False, indent=1))
                    tmp_c.replace(cache_path)
                    tmp_s = snap_path.with_suffix(".json.tmp")
                    tmp_s.write_text(json.dumps(snap, ensure_ascii=False, indent=2))
                    tmp_s.replace(snap_path)
                    self._json({"ok": True, "filled": filled, "count": len(filled)})
                except Exception as e:
                    self._json({"ok": False, "error": str(e)}, status=400)
                return
            if self.path == "/api/local/replace":
                try:
                    body = self._read_body()
                    old_name = body.get("old", "").strip()
                    new_name = body.get("new", "").strip()
                    new_url = body.get("url", "").strip()
                    if not old_name or not new_name:
                        raise ValueError("old and new are required")
                    result = replace_skill(old_name, new_name, new_url)
                    self._json(
                        {
                            "ok": True,
                            "result": result,
                            "message": f"已用 {new_name} 替换 {old_name}",
                        }
                    )
                except Exception as e:
                    self._json({"ok": False, "error": str(e)}, status=400)
                return
            if self.path == "/api/install":
                try:
                    body = self._read_body()
                    name = body.get("name", "").strip()
                    url = body.get("url", "").strip()
                    # ponytail: smart multi-CLI install — targets list lets user pick
                    # claude / codex / opencode. Default = all three.
                    raw_targets = body.get("targets")
                    if raw_targets:
                        targets = [t.strip() for t in raw_targets if t.strip()]
                    else:
                        targets = None
                    force_update = bool(body.get("force_update", False))
                    result = install_skill_from_github(
                        name, url, targets=targets, force_update=force_update
                    )
                    # ponytail: build a per-CLI human-readable status string
                    statuses = [
                        f"  · {cli}: {info['status']} ({info['detail']})"
                        for cli, info in result["targets"].items()
                    ]
                    msg = f"{name}\n" + "\n".join(statuses)
                    invalidate_local_scan()  # 「已装」徽标立即生效，不等 60s TTL
                    self._json(
                        {
                            "ok": True,
                            "message": msg,
                            "cache": str(result["cache"]),
                            "cache_state": result["cache_state"],
                            "targets": result["targets"],
                        }
                    )
                except Exception as e:
                    self._json({"ok": False, "error": str(e)}, status=400)
                return
            if self.path == "/api/update":
                # ponytail: 2026-09 — 更新 = install 的 force_update 变体
                # （git fetch + reset --hard origin/HEAD，不重新 clone）。
                try:
                    body = self._read_body()
                    name = body.get("name", "").strip()
                    url = body.get("url", "").strip()
                    result = install_skill_from_github(
                        name, url, targets=body.get("targets"), force_update=True
                    )
                    statuses = [
                        f"  · {cli}: {info['status']} ({info['detail']})"
                        for cli, info in result["targets"].items()
                    ]
                    invalidate_local_scan()
                    self._json(
                        {
                            "ok": True,
                            "message": f"{name} 已更新\n" + "\n".join(statuses),
                            "cache_state": result["cache_state"],
                            "targets": result["targets"],
                        }
                    )
                except Exception as e:
                    self._json({"ok": False, "error": str(e)}, status=400)
                return
            if self.path == "/api/uninstall":
                # ponytail: 2026-09 — 卸载闭环：删软链接 + 缓存目录可选保留。
                try:
                    body = self._read_body()
                    name = body.get("name", "").strip()
                    result = uninstall_skill(name)
                    invalidate_local_scan()
                    self._json({"ok": True, "message": f"{name} 已卸载", "result": result})
                except Exception as e:
                    self._json({"ok": False, "error": str(e)}, status=400)
                return
            if self.path == "/api/install-cli":
                try:
                    body = self._read_body()
                    name = body.get("name", "").strip()
                    command = body.get("command", "").strip()
                    path = install_cli_wrapper(name, command)
                    self._json(
                        {"ok": True, "message": f"已创建 /{name} 命令", "path": path}
                    )
                except Exception as e:
                    self._json({"ok": False, "error": str(e)}, status=400)
                return
            # ponytail: 2026-09 — 本机 tab 核心端点。
            # /api/upgrade?name=owner/repo: 单个 skill 升级(同步返,前端 toast)。
            # /api/upgrade-all: 批量升级,后台 Popen(因为 ls-remote 慢),前端轮询 /api/install/status。
            if self.path == "/api/upgrade" or self.path.startswith("/api/upgrade?"):
                try:
                    from radar_pkg.install import upgrade_one
                    qs = urllib.parse.urlparse(self.path).query
                    name = urllib.parse.parse_qs(qs).get("name", [""])[0].strip()
                    if not name:
                        self._json({"ok": False, "error": "name query param required"},
                                   status=400)
                        return
                    result = upgrade_one(name)
                    status = 200 if result.get("ok") else 400
                    self._json(result, status=status)
                except Exception as e:
                    self._json({"ok": False, "error": str(e)}, status=400)
                return
            if self.path == "/api/upgrade-all":
                # ponytail: 2026-09 — 批量升级 fork 子进程异步跑(ls-remote 100 项 ~ 8 分钟,
                # 阻塞 handler 会让前端 spinner 失去响应)。
                try:
                    # ponytail: 2026-09 P3 修复 — handler 不写 install_status,
                    # 单点源改由 subprocess 写。旧实现 handler 写 total=n_up,
                    # subprocess 立刻覆盖 total=0 + label="扫描中",再算一遍可能 n_up=3,
                    # banner 跳 5 → 0 → 3 用户被骗。
                    # ponytail: 2026-09 P5 修复 — 加了 --upgradable JSON argv 后,
                    # subprocess 写 total 与 handler 算的 n_up 一致(都来自同一个 dict),
                    # 没有闪烁风险。handler 写 initial status 立即给前端反馈,
                    # 消除 "2-5s 无 banner" 窗口。
                    from radar_pkg.install import compute_upgradable
                    import datetime as _dt
                    local = detect_local_skills()
                    up = compute_upgradable(local.get("skills") or {})
                    n_up = sum(1 for v in up.values() if v.get("upgradable"))
                    if n_up == 0:
                        self._json({"ok": True, "skipped": True,
                                    "message": "没有可升级的 skill"})
                        return
                    _project_root = Path(__file__).resolve().parent.parent
                    log_fd = os.open(
                        core.DATA / "upgrade_all.log",
                        os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644,
                    )
                    import json as _json
                    subprocess.Popen(
                        [sys.executable, str(_project_root / "radar.py"),
                         "upgrade_all", "--upgradable", _json.dumps(up)],
                        cwd=str(_project_root),
                        stdout=log_fd, stderr=subprocess.STDOUT,
                        start_new_session=True, close_fds=True,
                    )
                    # ponytail: 写 initial status — 同 total,subprocess 写入只是覆盖
                    # current 0 → 0,label 微调(0/N → 升级 X),无 flash。
                    _core_local.write_install_status(
                        running=True, current=0, total=n_up,
                        label=f"升级全部 (0/{n_up})",
                        started_at=_dt.datetime.now().isoformat(timespec="seconds"),
                    )
                    self._json({"ok": True, "started": True,
                                "total": n_up,
                                "message": f"开始升级 {n_up} 个 skill"})
                except Exception as e:
                    self._json({"ok": False, "error": str(e)}, status=400)
                return
            if self.path == "/api/local/origin":
                try:
                    body = self._read_body()
                    kind = body.get("kind", "").strip()
                    name = body.get("name", "").strip()
                    url = body.get("url", "").strip()
                    desc_zh = body.get("desc_zh", "").strip()
                    desc_en = body.get("desc_en", "").strip()
                    entry = set_capability_origin(kind, name, url, desc_zh, desc_en)
                    self._json({"ok": True, "entry": entry})
                except Exception as e:
                    self._json({"ok": False, "error": str(e)}, status=400)
                return
            if self.path == "/api/crawl":
                # ponytail: file-lock guard — 409 instead of spawning a doomed subprocess
                if crawl_lock_held():
                    return self._json(
                        {"ok": False, "error": "crawl already running"}, status=409
                    )
                # ponytail: 2026-09 P3 修复 — TOCTOU:handler 检查 lock 之后 Popen 之前
                # 可能有第二个 Popen 跑过 lock check 进来 — 两个 Popen 启动的子进程
                # 都进 crawl(),一个拿锁跑、另一个 fail silent 死,浪费 spawn + 困惑 stderr。
                # 修法:handler 立刻写 lock(自写),子进程在 crawl() 里不再 acquire 改 release。
                from radar_pkg.crawl import (
                    acquire_crawl_lock as _acquire,
                    release_crawl_lock as _release,
                )
                if not _acquire():
                    return self._json(
                        {"ok": False, "error": "crawl already running"}, status=409
                    )
                # ponytail: fire-and-forget background crawl so UI doesn't block.
                # Log fd must be closed BEFORE Popen takes ownership so the parent doesn't
                # leak it on every /api/crawl request (long-running dev server accumulates fds).
                # ponytail: 2026-09 fix — 用 radar.py(根目录 facade,有 __main__ CLI),
                # 而不是 radar_pkg/serve.py(没有 __main__,spawn 出来啥也不做).
                log_fd = os.open(DATA / "crawl.log", os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
                _project_root = Path(__file__).resolve().parent.parent
                subprocess.Popen(
                    [sys.executable, str(_project_root / "radar.py"), "crawl"],
                    cwd=str(_project_root),
                    stdout=log_fd,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                    close_fds=True,
                )
                # ponytail: 2026-09 P3 — 子进程会自己重新 acquire(覆盖我们的 PID)。
                # 我们写下的 lock 仅用于把 handler 之间序列化;它会被子进程覆盖。
                # 30s 后若子进程还没覆盖(异常退出),自动清掉,免得 409 卡死。
                def _cleanup_handler_lock():
                    import time as _t
                    _t.sleep(30)
                    try:
                        if core.CRAWL_LOCK.exists():
                            pid = int(core.CRAWL_LOCK.read_text().strip())
                            if pid == os.getpid():
                                _release()
                    except (OSError, ValueError):
                        pass
                import threading as _thr
                _thr.Thread(target=_cleanup_handler_lock, daemon=True).start()
                return self._json(
                    {"ok": True, "message": "crawl started in background"}
                )
            # ponytail: 2026-09 — 手动触发 upgradable cache 重算。
            # POST 触发后台线程(立即返 200,不阻塞),GET 轮询状态。
            if self.path == "/api/local/refresh":
                try:
                    _status = _core_local.read_refresh_status()
                    if _status.get("computing"):
                        return self._json({"ok": True, "already_running": True})
                    import threading as _thr

                    def _do_refresh():
                        from radar_pkg.install import compute_upgradable as _cu
                        from radar_pkg.detect import detect_local_skills as _dls
                        def _cb(cur, total, name):
                            # ponytail: 2026-09 — 进度回调,前端 banner
                            # 显示「5/292 正在检查 X」实时反馈。
                            try:
                                _core_local.set_refresh_status(
                                    computing=True, current=cur, total=total,
                                    current_name=name,
                                )
                            except Exception:
                                pass
                        try:
                            _core_local.set_refresh_status(
                                computing=True,
                                current=0, total=0,
                                started_at=datetime.datetime.now().isoformat(timespec="seconds"),
                            )
                            _local = _dls()
                            _payload = _cu(_local.get("skills") or {}, progress_callback=_cb)
                            _core_local.write_upgradable_cache(_payload)
                        except Exception as exc:
                            _core_local.set_refresh_status(
                                computing=False,
                                error=f"{type(exc).__name__}: {exc}",
                            )
                        else:
                            _core_local.set_refresh_status(computing=False, error=None)

                    _thr.Thread(target=_do_refresh, daemon=True, name="manual-refresh").start()
                    return self._json({"ok": True, "started": True})
                except Exception as e:
                    return self._json({"ok": False, "error": str(e)}, status=500)
            # ponytail: 2026-09 P3 — /api/llm/summarize 触发 LLM 5 桶分析。
            # 前端 Settings 抽屉按钮调此端点,后端 spawn `radar.py summarize` 后台跑。
            # 与 /api/crawl 同款:409 if running, Popen 拿 fd 后立刻关,start_new_session 防 ctrl-c。
            if self.path == "/api/llm/summarize":
                if summarize_lock_held():
                    return self._json(
                        {"ok": False, "error": "summarize already running"}, status=409
                    )
                from radar_pkg import settings as _settings
                provider, fields = _settings.active_config()
                # ponytail: 2026-09 — 与 /api/llm/status 同口径,要求 provider 必填字段已填。
                configured = False
                if provider == "anthropic":
                    configured = bool(fields.get("api_key"))
                elif provider == "openai":
                    configured = bool(fields.get("api_key")) and bool(fields.get("base_url"))
                elif provider == "ollama":
                    configured = bool(fields.get("host"))
                if not configured:
                    return self._json(
                        {"ok": False,
                         "error": "no LLM provider configured — open Settings drawer first"},
                        status=400,
                    )
                log_fd = os.open(DATA / "summarize.log", os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
                _project_root = Path(__file__).resolve().parent.parent
                proc = subprocess.Popen(
                    [sys.executable, str(_project_root / "radar.py"), "summarize"],
                    cwd=str(_project_root),
                    stdout=log_fd,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                    close_fds=True,
                )
                # ponytail: 2026-09 — 写 PID 到 llm_status.json,前端 cancel 端点靠它
                # 找进程并 kill。set_refresh_status 类似机制但写 llm_status.json。
                try:
                    core.write_install_status(
                        running=True, current=0, total=0, label="生成 5 桶",
                        started_at=datetime.datetime.now().isoformat(timespec="seconds"),
                    )
                    # ponytail: pid 单独存到 LLM_STATUS_PATH 外的辅助文件 —
                    # 写 PID 不会污染 install_status 的字段语义
                    pid_path = core.DATA / "summarize.pid"
                    pid_path.write_text(str(proc.pid))
                except Exception:
                    pass
                return self._json(
                    {"ok": True, "message": "summarize started in background",
                     "provider": provider, "pid": proc.pid}
                )
            # ponytail: 2026-09 — 用户主动取消。读 pid 文件 → kill 进程组
            # (start_new_session=True 时,kill PID 不够,要 killpg)→ 写 status 标志取消。
            if self.path == "/api/llm/cancel":
                try:
                    pid_path = core.DATA / "summarize.pid"
                    pid = int(pid_path.read_text().strip()) if pid_path.exists() else 0
                    if pid <= 0 or not _pid_alive(pid):
                        return self._json({"ok": False, "error": "summarize not running"})
                    # killpg 保证子进程组里的所有线程/子进程一起结束,而不是漏
                    # LLM 客户端的 keep-alive 连接/超时重试
                    try:
                        os.killpg(pid, _signal.SIGTERM)
                    except (OSError, ProcessLookupError, AttributeError):
                        # 退化: 退到单进程 kill(老 OS / macOS 不一定支持 killpg)
                        os.kill(pid, _signal.SIGTERM)
                    # ponytail: 给 3s 软退出 → 还没死就 SIGKILL。卡死的 LLM 调用
                    # 不响应 SIGTERM,只能硬杀。
                    for _ in range(30):
                        if not _pid_alive(pid):
                            break
                        time.sleep(0.1)
                    else:
                        try: os.kill(pid, _signal.SIGKILL)
                        except Exception: pass
                    core.write_install_status(
                        running=False, current=0, total=0,
                        label="生成 5 桶 (已取消)",
                        finished_at=datetime.datetime.now().isoformat(timespec="seconds"),
                        error="cancelled by user",
                    )
                    return self._json({"ok": True, "cancelled": True, "pid": pid})
                except Exception as e:
                    return self._json({"ok": False, "error": str(e)}, status=500)
            self.send_error(404)

    # ponytail: bind host configurable via RADAR_HOST env (default 127.0.0.1).
    # — local dev: keep loopback; — server deploy: set RADAR_HOST=0.0.0.0 and
    #   put a reverse proxy (nginx/caddy) in front for TLS + auth.
    # ponytail: 0.0.0.0 binding is intentionally opt-in — this API can git-clone
    # into users' skill dirs, so the safe default stays loopback.
    import errno as _errno
    bind_host = os.environ.get("RADAR_HOST", "127.0.0.1")
    actual_port = port
    httpd = None
    for offset in range(50):
        try_port = port + offset
        try:
            httpd = socketserver.ThreadingTCPServer((bind_host, try_port), Handler)
        except OSError as e:
            if e.errno == _errno.EADDRINUSE:
                continue
            raise
        actual_port = try_port
        break
    if httpd is None:
        raise SystemExit(f"no free port in [{port}..{port + 49}] for radar.py serve")

    with httpd:
        url = f"http://localhost:{actual_port}"
        if actual_port != port:
            print(
                f"[serve] requested port {port} busy, bound to {actual_port} instead",
                file=sys.stderr,
            )
        # ponytail: machine-parseable port line for dev.cjs — keep the format stable.
        print(f"[serve-port] {actual_port}", flush=True)
        print(
            f"[serve] {url}  (loopback only · API: /api/data /api/local /api/top /api/install /api/crawl /api/llm/summarize /api/llm/status · Ctrl-C to stop)"
        )
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[serve] stopped")

def web(port=8765):
    """一键打开仪表盘：已在跑就直接开浏览器；否则后台拉起 serve 再开。
    /zp 的默认入口 — 免去手动 serve + 开浏览器两步。"""
    import webbrowser

    def radar_alive(p: int) -> bool:
        # ponytail: 不只探端口 — / 返回 HTML（带静态托管的新版 serve）且
        # /api/data 可达才是 lodestone；旧版纯 API 或无关服务都不算，
        # 端口被占时自动落到下一端口新起一个
        # ponytail: ProxyHandler({}) 强制直连 — 用户 shell 可能挂 HTTP 代理，
        # urlopen 默认走代理会把 loopback 健康检查挂死
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(f"http://127.0.0.1:{p}/", timeout=1) as r:
                if r.status != 200 or "html" not in (r.headers.get("Content-Type") or ""):
                    return False
            with opener.open(f"http://127.0.0.1:{p}/api/data", timeout=1) as r:
                return r.status == 200
        except Exception:
            return False

    alive = next((p for p in range(port, port + 50) if radar_alive(p)), None)
    if alive is None:
        # ponytail: detached spawn，与 /api/crawl 同款 — start_new_session 脱离
        # /zp 的 Bash 会话，本命令返回后 serve 继续活着
        log_fd = os.open(DATA / "serve.log", os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "serve", str(port)],
            cwd=str(Path(__file__).parent.resolve()),
            stdout=log_fd,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )
        os.close(log_fd)  # ponytail: Popen 已 dup — 父进程立刻关，防 fd 泄漏
        for _ in range(100):  # 10s 上限等端口就绪（serve 端口被占会顺延）
            alive = next((p for p in range(port, port + 50) if radar_alive(p)), None)
            if alive:
                break
            time.sleep(0.1)
        if alive is None:
            raise SystemExit(f"serve did not come up — see {DATA / 'serve.log'}")
    # ponytail: 显式 127.0.0.1 而非 localhost — macOS 浏览器可能优先解析 IPv6 ::1，
    # 若 ::1 同端口被别的服务占着（本机就发生过：synapse 文档服务在 *:8765），
    # localhost 会打开错页面。serve 只绑 IPv4 loopback，127.0.0.1 必定命中。
    url = f"http://127.0.0.1:{alive}"
    print(f"⚡ Lodestone → {url}")
    webbrowser.open(url)
