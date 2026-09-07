#!/usr/bin/env bash
# install.sh — install lodestone as a skill for Claude Code AND Codex CLI
#
# Strategy: symlink (not copy) — single source of truth, no duplication
# of data/, node_modules/, etc. Both ~/.claude/skills/ and ~/.codex/skills/
# point back to this project directory.

set -e
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAME="zp"

CLAUDE_DIR="${HOME}/.claude/skills"
CODEX_DIR="${HOME}/.codex/skills"

ok()   { printf "  \033[32m✓\033[0m %s\n" "$*"; }
warn() { printf "  \033[33m!\033[0m %s\n" "$*"; }
fail() { printf "  \033[31m✗\033[0m %s\n" "$*"; exit 1; }

echo ""
echo "⚡ Lodestone · GitHub + HuggingFace 双源 AI 工具发现平台"
echo "   源目录: $HERE"
echo ""

# --- Pre-flight ---
[ -f "$HERE/SKILL.md" ] || fail "SKILL.md not found in $HERE"
[ -x "$HERE/radar.py" ] || chmod +x "$HERE/radar.py"

# --- Claude Code ---
echo "📦 Claude Code ($CLAUDE_DIR/$NAME)"
mkdir -p "$CLAUDE_DIR"
if [ -L "$CLAUDE_DIR/$NAME" ]; then
  warn "已存在 symlink → $(readlink "$CLAUDE_DIR/$NAME")，重新指向"
  rm "$CLAUDE_DIR/$NAME"
elif [ -e "$CLAUDE_DIR/$NAME" ]; then
  warn "已存在实体目录，备份为 ${NAME}.bak"
  mv "$CLAUDE_DIR/$NAME" "${CLAUDE_DIR}/${NAME}.bak.$(date +%s)"
fi
ln -s "$HERE" "$CLAUDE_DIR/$NAME"
ok "symlinked"

# --- Codex CLI ---
echo ""
echo "📦 Codex CLI ($CODEX_DIR/$NAME)"
mkdir -p "$CODEX_DIR"
if [ -L "$CODEX_DIR/$NAME" ]; then
  warn "已存在 symlink → $(readlink "$CODEX_DIR/$NAME")，重新指向"
  rm "$CODEX_DIR/$NAME"
elif [ -e "$CODEX_DIR/$NAME" ]; then
  warn "已存在实体目录，备份为 ${NAME}.bak"
  mv "$CODEX_DIR/$NAME" "${CODEX_DIR}/${NAME}.bak.$(date +%s)"
fi
ln -s "$HERE" "$CODEX_DIR/$NAME"
ok "symlinked"

echo ""
echo "🎉 安装完成！"
echo ""
echo "触发方式："
echo "  Claude Code → 直接说：「刷一下 AI 雷达」「最近有什么 AI 项目」"
echo "  Codex CLI   → 直接说：「刷一下 AI 雷达」「最近有什么 AI 项目」"
echo ""
echo "手动调用："
echo "  $HERE/radar.py crawl    # 爬取 + 入库（约 5-8 分钟）"
echo "  $HERE/radar.py today    # 终端看 Top 15"
echo ""
echo "卸载："
echo "  $HERE/uninstall.sh"
echo ""
