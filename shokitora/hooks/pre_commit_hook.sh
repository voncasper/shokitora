#!/usr/bin/env bash
# Shokitora Git Pre-Commit Hook - Zero Plaintext Secret Guardrail
# ===============================================================
# Prevents accidental commits of plaintext .env files or hardcoded
# API access tokens (GitHub PATs, OpenAI keys, Slack tokens).

set -e

# 1. Block staging of plaintext .env files
STAGED_ENV_FILES=$(git diff --cached --name-only | grep -E '(^|/)\.env($|\..*)' || true)
if [ -n "$STAGED_ENV_FILES" ]; then
    echo ""
    echo "❌ [Shokitora Guardrail Blocked] Plaintext .env file staged for commit:"
    echo "   $STAGED_ENV_FILES"
    echo ""
    echo "   Shokitora enforces a strict Zero-Plaintext Secrets policy."
    echo "   Eliminate this plaintext file using the hardware-bound Sovereign Vault:"
    echo ""
    echo "   1. Import into vault and shred file:  shoki vault import-env .env --delete-source"
    echo "   2. Unstage the deleted file:          git rm --cached .env"
    echo "   3. Run applications via RAM:          shoki vault run -- python3 app.py"
    echo ""
    exit 1
fi

# 2. Scan staged diffs for high-risk token patterns
HIGH_RISK_DIFF=$(git diff --cached -U0 | grep -E '^\+[^+].*(ghp_[A-Za-z0-9]{36}|sk-proj-[A-Za-z0-9_-]{40,}|xoxb-[A-Za-z0-9_-]+)' || true)
if [ -n "$HIGH_RISK_DIFF" ]; then
    echo ""
    echo "❌ [Shokitora Guardrail Blocked] Hardcoded API token pattern detected in staged changes!"
    echo "   Matches: $HIGH_RISK_DIFF"
    echo ""
    echo "   Do not commit raw API keys into source control."
    echo "   Store secrets securely in the Sovereign Vault instead:"
    echo "   shoki vault set <service/token> <value> --expires-in 90d"
    echo ""
    exit 1
fi

exit 0
