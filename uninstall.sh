#!/usr/bin/env bash
# uninstall.sh — remove lodestone (formerly yz-ai / zp) symlinks from skills dirs
# and OpenCode command/ wrappers.

set -e
NAMES=(lodestone zp yz-ai)

remove_symlink() {
    local target="$1"
    if [ -L "$target" ]; then
        rm "$target"
        echo "  ✓ removed $target"
    elif [ -e "$target" ]; then
        echo "  ! $target exists but is not a symlink (skipping)"
    else
        echo "  · $target not installed"
    fi
}

remove_file() {
    local target="$1"
    if [ -e "$target" ]; then
        rm "$target"
        echo "  ✓ removed $target"
    else
        echo "  · $target not installed"
    fi
}

echo "🧹 Removing lodestone skill symlinks..."
for D in \
    "${HOME}/.claude/skills" \
    "${HOME}/.codex/skills" \
    "${HOME}/.config/opencode/skills" \
    "${HOME}/.easycode/skills"; do
    echo ""
    echo "📦 $D"
    for n in "${NAMES[@]}"; do
        remove_symlink "$D/$n"
    done
done

echo ""
echo "📦 ${HOME}/.config/opencode/command  (OpenCode slash-command wrappers)"
for n in "${NAMES[@]}"; do
    remove_file "${HOME}/.config/opencode/command/$n.md"
done

echo ""
echo "🎉 卸载完成。"
