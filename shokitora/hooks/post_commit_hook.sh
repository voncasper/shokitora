#!/usr/bin/env bash
# Shokitora Git Post-Commit Hook
# Automatically logs technical decisions and learnings to the local ledger.

COMMIT_MSG=$(git log -1 --pretty=%B)
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")

if command -v shoki &> /dev/null; then
    shoki add learning "Git Commit [$BRANCH]: $COMMIT_MSG" 2>/dev/null || true
elif command -v scribe &> /dev/null; then
    scribe add learning "Git Commit [$BRANCH]: $COMMIT_MSG" 2>/dev/null || true
fi
