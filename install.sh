#!/usr/bin/env bash
# install.sh — install lodestone as a skill for Claude Code AND Codex CLI
#
# Strategy: symlink (not copy) — single source of truth, no duplication
# of data/, node_modules/, etc. Both ~/.claude/skills/ and ~/.codex/skills/
# point back to this project directory.

set -e
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# ponytail: 2026-09 — skill 名从 zp 改为 yz-ai; /yz:ai 命令暴露.
# 旧的 ~/.claude/skills/zp 仍可通过同名 symlink 保留.
NAME="yz-ai"

CLAUDE_DIR="${HOME}/.claude/skills"
CODEX_DIR="${HOME}/.codex/skills"
OPENCODE_DIR="${HOME}/.config/opencode/skills"
EASYCODE_DIR="${HOME}/.easycode/skills"

ok()   { printf "  \033[32m✓\033[0m %s\n" "$*"; }
warn() { printf "  \033[33m!\033[0m %s\n" "$*"; }
fail() { printf "  \033[31m✗\033[0m %s\n" "$*"; exit 1; }

echo ""
echo "⚡ Lodestone · /yz:ai skill (Claude Code + Codex + OpenCode + EasyCode)"
echo "   源目录: $HERE"
echo ""

# --- Pre-flight ---
[ -f "$HERE/SKILL.md" ] || fail "SKILL.md not found in $HERE"
[ -x "$HERE/radar.py" ] || chmod +x "$HERE/radar.py"

# --- helper: symlink one CLI target, ignore if dir doesn't exist ---
link_one() {
    local label="$1"; local dir="$2"; local legacy="$3"
    echo ""
    echo "📦 $label ($dir/$NAME)"
    mkdir -p "$dir" 2>/dev/null || true
    [ -d "$dir" ] || { warn "目录不存在,跳过 ($dir)"; return 0; }
    if [ -L "$dir/$NAME" ]; then
        warn "已存在 symlink → $(readlink "$dir/$NAME")，重新指向"
        rm "$dir/$NAME"
    elif [ -e "$dir/$NAME" ]; then
        warn "已存在实体目录,备份为 ${NAME}.bak"
        mv "$dir/$NAME" "${dir}/${NAME}.bak.$(date +%s)"
    fi
    ln -s "$HERE" "$dir/$NAME"
    ok "symlinked"
    # legacy zp symlink for backwards compat
    if [ -n "$legacy" ] && [ ! -e "$dir/$legacy" ]; then
        ln -s "$HERE" "$dir/$legacy" 2>/dev/null && ok "legacy $legacy 也建好" || true
    fi
}

link_one "Claude Code"  "$CLAUDE_DIR"   "zp"
link_one "Codex CLI"    "$CODEX_DIR"    "zp"
link_one "OpenCode"     "$OPENCODE_DIR" "zp"
link_one "EasyCode"     "$EASYCODE_DIR" "zp"

echo ""
echo "🎉 安装完成!"
echo ""
echo "触发方式:"
echo "  Claude Code → 输入: /yz:ai"
echo "  Codex CLI   → 输入: /yz:ai"
echo "  OpenCode    → 输入: /yz:ai"
echo "  EasyCode    → 输入: /yz:ai"
echo ""
echo "手动调用:"
echo "  $HERE/radar.py web      # 一键仪表盘(后台起 serve + 打开浏览器)"
echo "  $HERE/radar.py crawl    # 爬取 + 入库(约 5-8 分钟)"
echo "  $HERE/radar.py today    # 终端看 Top 15"
echo ""
echo "卸载:"
echo "  $HERE/uninstall.sh"
echo ""
