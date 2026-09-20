#!/usr/bin/env bash
# Shokitora Git Post-Commit Hook
# ==============================
# Automatically logs technical activity to the local SQLite engineering ledger.

COMMIT_HASH=$(git log -1 --pretty=%h)
COMMIT_MSG=$(git log -1 --pretty=%B | tr '\n' ' ' | sed -e 's/[[:space:]]*$//')
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")

# Determine category: if commit starts with 'arch:' or 'decide:' -> decision; otherwise learning
CATEGORY="learning"
if [[ "$COMMIT_MSG" =~ ^(arch|decision|decide): ]]; then
    CATEGORY="decision"
fi

CONTENT="Git Commit [$BRANCH $COMMIT_HASH]: $COMMIT_MSG"

# Check if commit message links to a task (e.g., #123)
PARENT_FLAG=""
if [[ "$COMMIT_MSG" =~ \#([0-9]+) ]]; then
    TASK_ID="${BASH_REMATCH[1]}"
    PARENT_FLAG="--parent $TASK_ID"
fi

# Execute log entry via shoki / scribe CLI or python module fallback
if command -v shoki &> /dev/null; then
    shoki add "$CATEGORY" "$CONTENT" $PARENT_FLAG 2>/dev/null || true
elif command -v scribe &> /dev/null; then
    scribe add "$CATEGORY" "$CONTENT" $PARENT_FLAG 2>/dev/null || true
elif command -v python3 &> /dev/null; then
    python3 -m shokitora.cli.main add "$CATEGORY" "$CONTENT" $PARENT_FLAG 2>/dev/null || true
fi
