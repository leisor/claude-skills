#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR="$HOME/.claude/skills/mattpocock-skills"
BACKUP_DIR="$HOME/.claude/skills/.backup-$(date +%Y-%m-%d-%H%M%S)"

echo "Claude Skills Installer"
echo "======================="
echo "Repo:   $REPO_DIR"
echo "Target: $TARGET_DIR"
echo ""

mkdir -p "$HOME/.claude/skills"

# Backup existing if it's not our symlink
if [ -e "$TARGET_DIR" ] && [ ! -L "$TARGET_DIR" ]; then
    echo "Backing up existing directory to $BACKUP_DIR ..."
    mkdir -p "$BACKUP_DIR"
    mv "$TARGET_DIR" "$BACKUP_DIR/"
fi

# Remove old symlink if present
rm -f "$TARGET_DIR"

# Create symlink
ln -sf "$REPO_DIR" "$TARGET_DIR"
echo "Symlink created: $TARGET_DIR -> $REPO_DIR"

# Install workflow-gate CLI
mkdir -p "$HOME/.local/bin"
ln -sf "$REPO_DIR/scripts/workflow-gate" "$HOME/.local/bin/workflow-gate"
chmod +x "$REPO_DIR/scripts/workflow-gate"
echo "CLI installed: $HOME/.local/bin/workflow-gate"

# Remove remote marketplace plugin if installed
echo "Checking for remote plugin..."
claude plugin uninstall mattpocock-skills@mattpocock 2>/dev/null || true

# Validate
echo "Validating plugin..."
claude plugin validate "$REPO_DIR"

echo ""
echo "Done! Matt Pocock skills with custom review gates are now globally active in Claude Code."
