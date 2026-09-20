# Shokitora Git Hooks Setup & Automation Guide

**Version:** 0.1.1  
**Author:** Vincent Capers Jr., Founder & Principal Architect  
**Corporate Entity:** VonCasper Solutions  
**Part of:** Shokitora (書記虎) Open-Source Architecture  

---

## 1. Overview & Architectural Purpose

Git hooks are lifecycle scripts that execute automatically during Git events (such as `git commit` or `git push`). In traditional development setups, developers either forget to document their work or rely on cumbersome external forms. Furthermore, developers frequently commit plaintext `.env` files or API tokens by accident.

**Shokitora provides two zero-friction Git hooks:**

```
                   [ git commit ]
                         │
                         ▼
        ┌──────────────────────────────────┐
        │  1. PRE-COMMIT HOOK (Guardrail)  │
        │     - Blocks plaintext .env      │
        │     - Blocks raw API key strings │
        └──────────────────────────────────┘
                         │ (Success)
                         ▼
        ┌──────────────────────────────────┐
        │       Commit Object Created      │
        └──────────────────────────────────┘
                         │
                         ▼
        ┌──────────────────────────────────┐
        │ 2. POST-COMMIT HOOK (Automation) │
        │    - Logs commit to journal.db   │
        │    - Auto-links to task #ID      │
        │    - Classifies decision/learning│
        └──────────────────────────────────┘
```

1. **`pre-commit` (Zero-Leak Security Guardrail):** Intercepts staged files before commit creation. Blocks accidental staging of plaintext `.env` files and high-risk API key patterns (`ghp_`, `sk-proj-`, `xoxb-`), pointing developers to the hardware-bound Sovereign Vault.
2. **`post-commit` (Automated Technical Journaling):** Executes after every successful commit to extract context, link commits to active sprint tasks, and append learnings or architectural decisions to Shokitora's SQLite ledger (`journal.db`).

---

## 2. Quickstart: 1-Line Installation

Shokitora includes a built-in hooks manager directly in the CLI:

```bash
# Navigate to your project root (must be a Git repository)
cd /path/to/my-project

# Install both pre-commit and post-commit hooks
shoki hooks install
```

Output:
```
🐯 Shokitora Git Hooks Installed Successfully!
============================================================
  ✓ .git/hooks/pre-commit
  ✓ .git/hooks/post-commit

Protections Active:
  • pre-commit  : Prevents committing plaintext .env files & raw tokens
  • post-commit : Automatically logs commits into Shokitora technical ledger
```

### Checking Hook Health
Verify that hooks are active and marked executable:
```bash
shoki hooks status
```

Output:
```
🐯 Shokitora Git Hooks Status
============================================================
  • pre-commit     : ACTIVE (Executable)
  • post-commit    : ACTIVE (Executable)
```

### Uninstalling Hooks
If you ever need to remove Shokitora hooks from your repository:
```bash
shoki hooks uninstall
```

---

## 3. The Pre-Commit Guardrail (`pre-commit`)

The pre-commit guardrail acts as an automated security filter running locally on your workstation. It performs two strict checks:

### 3.1 Plaintext `.env` File Detection
If any file matching `.env*` (e.g. `.env`, `.env.local`, `.env.production`) is staged for commit, the hook aborts execution:

```bash
$ git add .env
$ git commit -m "chore: add environment config"

❌ [Shokitora Guardrail Blocked] Plaintext .env file staged for commit:
   .env

   Shokitora enforces a strict Zero-Plaintext Secrets policy.
   Eliminate this plaintext file using the hardware-bound Sovereign Vault:

   1. Import into vault and shred file:  shoki vault import-env .env --delete-source
   2. Unstage the deleted file:          git rm --cached .env
   3. Run applications via RAM:          shoki vault run -- python3 app.py
```

### 3.2 High-Risk Token Pattern Scanning
The hook scans the staged diff (`git diff --cached`) for high-entropy token prefixes:
- `ghp_...` (GitHub Personal Access Tokens)
- `sk-proj-...` (OpenAI Project Secret Keys)
- `xoxb-...` (Slack Bot User Tokens)

If a match is found:
```bash
❌ [Shokitora Guardrail Blocked] Hardcoded API token pattern detected in staged changes!
   Matches: +GITHUB_TOKEN = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"

   Do not commit raw API keys into source control.
   Store secrets securely in the Sovereign Vault instead:
   shoki vault set <service/token> <value> --expires-in 90d
```

### 3.3 Emergency Override
In exceptional circumstances where a commit must bypass the pre-commit check (e.g., committing synthetic test fixture tokens), use Git's standard bypass flag:
```bash
git commit --no-verify -m "test: add mock dummy token fixtures"
```

---

## 4. The Post-Commit Journaling Hook (`post-commit`)

The post-commit hook converts routine developer activity into a persistent, queryable knowledge base. Every time `git commit` completes, the hook triggers silently in the background.

### 4.1 Automatic Classification
The hook analyzes the commit message header:
- If the commit message starts with `arch:`, `decision:`, or `decide:`:
  The entry is automatically categorized as an **Architectural Decision** (`decision`).
- For standard commits (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`):
  The entry is automatically categorized as a **Technical Learning** (`learning`).

### 4.2 Automated Task Linking
If your commit message references a Shokitora task ID using `#<ID>`:
```bash
git commit -m "feat(vault): add relative expiration parsing #42"
```

The post-commit hook extracts `#42` and links the new journal entry as a child to Task `#42`.

When you run `shoki task:list`, Task `#42` shows the linked commit:
```
#42 [2026-09-20] TASK [IN_PROGRESS]: Implement Vault Expiration Engine [Sprint: Sprint 1]
    └── Children: #58 LEARNING (Git Commit [main a1b2c3d]: feat(vault): add relative expiration parsing #42)
```

---

## 5. Manual Hook Installation (No-CLI Environments)

If you are setting up hooks in an air-gapped CI runner or without the `shoki` binary in your PATH, you can install the hooks manually using standard bash scripts:

### Method A: Copy Hook Scripts Directly
```bash
# From the Shokitora repository root:
cp shokitora/hooks/pre_commit_hook.sh .git/hooks/pre-commit
cp shokitora/hooks/post_commit_hook.sh .git/hooks/post-commit

chmod +x .git/hooks/pre-commit
chmod +x .git/hooks/post-commit
```

### Method B: Symlink Hooks (Multi-Developer Shared Workspaces)
To ensure all local branches track updates to hook scripts:
```bash
ln -sf "$(pwd)/shokitora/hooks/pre_commit_hook.sh" .git/hooks/pre-commit
ln -sf "$(pwd)/shokitora/hooks/post_commit_hook.sh" .git/hooks/post-commit

chmod +x .git/hooks/*
```

### Method C: Repository-Wide `core.hooksPath`
Configure Git to look inside a version-controlled `.githooks` directory:
```bash
mkdir -p .githooks
cp shokitora/hooks/*.sh .githooks/
chmod +x .githooks/*

git config core.hooksPath .githooks
```

---

## 6. Autonomous AI Agent Hook Interactions

When autonomous AI coding agents (such as Google Antigravity, Claude Code, or Hermes) operate in your repository:

1. **Passive Telemetry:** The agent does not need to be instructed to log every minor commit. The `post-commit` hook records commit hashes, branches, and summaries automatically in `journal.db`.
2. **Instant Rollback Guard:** If an AI agent attempts to generate a `.env` file or hardcode a decrypted secret from its prompt context into code, the `pre-commit` hook instantly aborts the commit before any secret touches the Git tree.
3. **Audit Readiness:** When reviewing work done by an AI agent, you can inspect `shoki task:history <task_id>` to view every state transition, linked commit, and logged hour.

---

## 7. Troubleshooting

| Issue | Cause | Solution |
|---|---|---|
| Hook does not run | File lacks execute permission | Run `chmod +x .git/hooks/*` |
| `command not found: shoki` | Python bin directory not in PATH | Install hook with fallback or run `pip install -e .` |
| Blocked by false-positive token | Mock token in test file | Use `git commit --no-verify` for verified test mocks |
| Hook runs in wrong git repo | Multiple worktrees or submodules | Run `shoki hooks install` from the exact target repo root |
