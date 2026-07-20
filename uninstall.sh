#!/usr/bin/env bash
# uninstall.sh — remove lodestone symlinks from both skills dirs
set -e
NAME="lodestone"
for D in "${HOME}/.claude/skills" "${HOME}/.codex/skills"; do
  if [ -L "$D/$NAME" ]; then
    rm "$D/$NAME"
    echo "  ✓ removed $D/$NAME"
  elif [ -e "$D/$NAME" ]; then
    echo "  ! $D/$NAME exists but is not a symlink (skipping)"
  else
    echo "  · $D/$NAME not installed"
  fi
done