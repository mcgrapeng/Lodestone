#!/usr/bin/env bash
# install.sh — install yz-ai (formerly lodestone / zp) as a skill for
# Claude Code / Codex CLI / OpenCode / EasyCode.
#
# Strategy: symlink (not copy) — single source of truth, no duplication
# of data/, node_modules/, etc. Skills point back to this project directory.
#
# OpenCode 还需要 command/<name>.md 包装文件才能注册 /yz-ai 斜杠命令
# (OpenCode 的 skills/ 与 commands/ 是两个目录，不像 Claude 那样合一).
# ponytail: 2026-09 — 旧项目名 lodestone / zp 的 legacy symlink 仍然建，用于老用户
# 升级时无缝衔接。新用户 clone 后这两个目录不存在,自动跳过,无副作用。

set -e
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# ponytail: 2026-09 — 主命令名 yz-ai; lodestone / zp 变 legacy alias.
# /yz-ai 是航海家用磁石导航 — 这个 skill 是 AI 工程师的"磁石":
# 穿过 4 个数据洋流 (GitHub/HF/MCP/arXiv),把你引到该用的人工工具上.
# 旧的 ~/.claude/skills/lodestone / zp 仍可通过同名 symlink 保留.
NAME="yz-ai"

CLAUDE_DIR="${HOME}/.claude/skills"
CODEX_DIR="${HOME}/.codex/skills"
OPENCODE_SKILLS_DIR="${HOME}/.config/opencode/skills"
OPENCODE_COMMAND_DIR="${HOME}/.config/opencode/command"
EASYCODE_DIR="${HOME}/.easycode/skills"

ok()   { printf "  \033[32m✓\033[0m %s\n" "$*"; }
warn() { printf "  \033[33m!\033[0m %s\n" "$*"; }
fail() { printf "  \033[31m✗\033[0m %s\n" "$*"; exit 1; }

echo ""
echo "⚡ Lodestone · /yz-ai skill (Claude Code + Codex + OpenCode + EasyCode)"
echo "   源目录: $HERE"
echo ""

# --- Pre-flight ---
[ -f "$HERE/SKILL.md" ] || fail "SKILL.md not found in $HERE"
[ -x "$HERE/radar.py" ] || chmod +x "$HERE/radar.py"

# --- helper: symlink one CLI target, ignore if dir doesn't exist ---
# Args: label, dir, legacy1, legacy2
link_one() {
    local label="$1"; local dir="$2"
    local legacy1="$3"; local legacy2="$4"
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
    # legacy 名称 symlink 兼容老用户(lodestone / zp 都指向新 yz-ai)
    if [ -n "$legacy1" ] && [ ! -e "$dir/$legacy1" ]; then
        ln -s "$HERE" "$dir/$legacy1" 2>/dev/null && ok "legacy $legacy1 也建好" || true
    fi
    if [ -n "$legacy2" ] && [ ! -e "$dir/$legacy2" ]; then
        ln -s "$HERE" "$dir/$legacy2" 2>/dev/null && ok "legacy $legacy2 也建好" || true
    fi
}

# --- helper: install OpenCode slash-command wrappers ---
# OpenCode 需要独立的 command/<name>.md 文件才能注册 /<name> 命令,
# skill 本身在 skills/<name>/SKILL.md,两边缺一不可.
install_opencode_commands() {
    local cmd_dir="$1"; local legacy1="$2"; local legacy2="$3"
    echo ""
    echo "📦 OpenCode slash commands ($cmd_dir)"
    mkdir -p "$cmd_dir" 2>/dev/null || true
    [ -d "$cmd_dir" ] || { warn "目录不存在,跳过 ($cmd_dir)"; return 0; }
    install_one_command() {
        local name="$1"
        local src="$HERE/command/$name.md"
        local dst="$cmd_dir/$name.md"
        [ -f "$src" ] || { warn "工程里缺 $src,跳过"; return 0; }
        if [ -e "$dst" ]; then
            if cmp -s "$src" "$dst"; then
                ok "$name.md 已就位且一致"
            else
                warn "$dst 已存在且内容不同,备份为 ${dst}.bak.$(date +%s)"
                mv "$dst" "${dst}.bak.$(date +%s)"
                cp "$src" "$dst"
                ok "$name.md 已更新"
            fi
        else
            cp "$src" "$dst"
            ok "$name.md 已建好"
        fi
    }
    install_one_command "$NAME"
    [ -n "$legacy1" ] && install_one_command "$legacy1"
    [ -n "$legacy2" ] && install_one_command "$legacy2"
}

link_one "Claude Code"  "$CLAUDE_DIR"          "lodestone" "zp"
link_one "Codex CLI"    "$CODEX_DIR"           "lodestone" "zp"
link_one "OpenCode"     "$OPENCODE_SKILLS_DIR" "lodestone" "zp"
link_one "EasyCode"     "$EASYCODE_DIR"        "lodestone" "zp"
install_opencode_commands "$OPENCODE_COMMAND_DIR" "lodestone" "zp"

echo ""
echo "🎉 安装完成!"
echo ""
echo "触发方式:"
echo "  Claude Code → /yz-ai   (旧名 /lodestone / /zp 仍可触发)"
echo "  Codex CLI   → \$yz:ai  (Codex 用 \$ 前缀,不是 /)"
echo "  OpenCode    → /yz-ai   (旧名 /lodestone / /zp 仍可触发)"
echo "  EasyCode    → /yz-ai"
echo ""
echo "自然语言触发(三家都支持,不用记命令):"
echo "  「看看最新AI项目」/「AI radar」/「刷一下AI雷达」/「最近有什么火的AI项目」"
echo ""
echo "手动调用:"
echo "  $HERE/radar.py web      # 一键仪表盘(后台起 serve + 打开浏览器)"
echo "  $HERE/radar.py crawl    # 爬取 + 入库(约 5-8 分钟)"
echo "  $HERE/radar.py today    # 终端看 Top 15"
echo ""
echo "卸载:"
echo "  $HERE/uninstall.sh"
echo ""
