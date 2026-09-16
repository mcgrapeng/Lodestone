# -*- coding: utf-8 -*-
"""radar_pkg.progress — stdlib 进度条 + 阶段日志。无外部依赖。

设计:
- 所有进度输出走 stderr(背景子进程不被 stdout pipe 缓冲), flush=True
- TTY 时 \r 覆盖当前行;非 TTY(管道/日志文件)时换行追加 — 便于 `tail -f`
- phase(label) 打印阶段标题; bar(label, i, total) 打印单条进度; eta(t0) 算耗时
- ponytail: 30 行 stdlib,只服务 crawl — 不发明通用框架
"""
from __future__ import annotations

import sys
import time


def _is_tty() -> bool:
    try:
        return sys.stderr.isatty()
    except Exception:
        return False


def _emit(s: str) -> None:
    sys.stderr.write(s)
    sys.stderr.flush()


def phase(label: str) -> None:
    """阶段标题 — 始终换行。"""
    _emit(f"\n── {label} ──\n")


def bar(label: str, i: int, total: int, width: int = 24) -> None:
    """进度条 — TTY 用 \\r 覆盖;非 TTY 换行追加。"""
    i = min(i, total)
    pct = (100 * i / total) if total else 100
    fill = int(width * i / total) if total else width
    cells = "█" * fill + "░" * (width - fill)
    line = f"  [{cells}] {pct:5.1f}%  {i}/{total}  {label}"
    if _is_tty():
        _emit("\r" + line + "  ")
    else:
        _emit(line + "\n")


def eta(t0: float, i: int, total: int) -> str:
    """从 t0 算已耗时 + 预计剩余。返回 ' (12s, ~18s left)' 这种片段。"""
    elapsed = time.monotonic() - t0
    if i <= 0 or total <= 0:
        return f" ({elapsed:.0f}s)"
    rate = i / elapsed
    left = max(0.0, (total - i) / rate) if rate > 0 else 0
    return f" ({elapsed:.0f}s, ~{left:.0f}s left)"


def log(msg: str) -> None:
    """普通日志 — 始终换行,flush。"""
    _emit(msg + "\n")


def done(msg: str) -> None:
    """完成行 — TTY 补换行避免残留。"""
    if _is_tty():
        _emit("\n")
    _emit(f"  ✓ {msg}\n")
