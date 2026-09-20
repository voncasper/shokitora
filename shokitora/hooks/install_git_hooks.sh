#!/usr/bin/env bash
# Installs the Shokitora post-commit hook into the current Git repository
set -e

GIT_DIR=$(git rev-parse --git-dir 2>/dev/null || echo "")
if [ -z "$GIT_DIR" ]; then
    echo "Error: Not a git repository. Run this command inside your project root."
    exit 1
fi

HOOK_FILE="$GIT_DIR/hooks/post-commit"
cp "$(dirname "$0")/post_commit_hook.sh" "$HOOK_FILE"
chmod +x "$HOOK_FILE"
echo "✓ Shokitora post-commit hook successfully installed to $HOOK_FILE"
