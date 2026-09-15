#!/usr/bin/env bash
# sync-skills.sh — 把当前 ~/.config/opencode/skills/ 全集 symlink 同步到
# ~/.claude/skills/ 和 ~/.codex/skills/(单一来源,不复制内容)。
#
# 策略:
#   - 已存在的 skill 全部跳过(不覆盖、不替换、不备份)
#   - 用 symlink,源指向 opencode 的 skill 路径(若本身已是 symlink,会透明解析)
#   - 跳过没有 SKILL.md 的项(opencode 装坏的包或非 skill 目录)
#   - 隐藏目录(.system / dotfile)跳过
#
# 用法:  ./sync-skills.sh [--dry-run]

set -euo pipefail

SRC="${HOME}/.config/opencode/skills"
DST_CLAUDE="${HOME}/.claude/skills"
DST_CODEX="${HOME}/.codex/skills"

DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

ok()   { printf "  \033[32m✓\033[0m %s\n" "$*"; }
skip() { printf "  \033[33m·\033[0m %s\n" "$*"; }
fail() { printf "  \033[31m✗\033[0m %s\n" "$*"; exit 1; }

[ -d "$SRC" ] || fail "源目录不存在: $SRC"
mkdir -p "$DST_CLAUDE" "$DST_CODEX"

added_claude=0; added_codex=0; skipped=0; broken_src=0

# 遍历源(symlink 跟随解析到真实路径,验证 SKILL.md)
shopt -s nullglob dotglob 2>/dev/null || true
for src_path in "$SRC"/*; do
    name="$(basename "$src_path")"
    case "$name" in
        .*|.system) continue ;;
    esac

    # 跳过非 SKILL: 没有 SKILL.md 的不进任何平台
    if [ ! -f "$src_path/SKILL.md" ]; then
        skip "源缺 SKILL.md,跳过: $name"
        skipped=$((skipped + 1))
        continue
    fi

    # 同步到 claude
    if [ ! -e "$DST_CLAUDE/$name" ]; then
        if [ "$DRY_RUN" -eq 1 ]; then
            echo "  [dry] ln -s $src_path $DST_CLAUDE/$name"
        else
            ln -s "$src_path" "$DST_CLAUDE/$name"
        fi
        added_claude=$((added_claude + 1))
    fi

    # 同步到 codex
    if [ ! -e "$DST_CODEX/$name" ]; then
        if [ "$DRY_RUN" -eq 1 ]; then
            echo "  [dry] ln -s $src_path $DST_CODEX/$name"
        else
            ln -s "$src_path" "$DST_CODEX/$name"
        fi
        added_codex=$((added_codex + 1))
    fi
done

echo ""
echo "📊 同步完成:"
echo "   → claude: 新增 $added_claude 个 symlink"
echo "   → codex:  新增 $added_codex 个 symlink"
echo "   ⊘ 跳过无 SKILL.md: $skipped 个"
[ "$DRY_RUN" -eq 1 ] && echo "   ⚠️  DRY RUN,未真正写入"
