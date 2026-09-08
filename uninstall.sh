#!/usr/bin/env bash
set -euo pipefail

TARGET_DIR="$HOME/.claude/skills/mattpocock-skills"

echo "Claude Skills Uninstaller"
echo "========================="

if [ -L "$TARGET_DIR" ]; then
    rm -f "$TARGET_DIR"
    echo "Removed symlink $TARGET_DIR"
fi

echo "To restore the official plugin, run:"
echo "claude plugin install mattpocock-skills@mattpocock"
