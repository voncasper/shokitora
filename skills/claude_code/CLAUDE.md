# Claude Code Engineering Guidelines (Shokitora Control Plane)

This repository is governed by **Shokitora (書記虎)** — a local-first engineering memory ledger and hardware-bound secrets vault.

## 🐯 Core Directives for Claude Code

1. **Pre-Task Grounding:**
   - Always inspect active sprint tasks at session start: `shoki task:list`
   - Check recent decisions before proposing new architectures: `shoki list --category decision --limit 5`
   - Check recent learnings to avoid known bugs: `shoki list --category learning --limit 5`

2. **Strict Zero Plaintext Secrets Policy:**
   - NEVER create, edit, or commit plaintext `.env` files.
   - NEVER print raw API keys or passwords into console outputs.
   - Inject secrets purely in memory: `shoki vault run -- <command>`
   - Audit stored keys if API errors occur: `shoki vault triage [service]`

3. **Post-Task Completion Routine:**
   - Mark task completed and log actual hours: `shoki update <id> --status COMPLETED --hours <N>`
   - Log architectural choices: `shoki add decision "<rationale>" --parent <id>`
   - Log edge cases / bug fixes: `shoki add learning "<solution>" --parent <id>`

## Common Commands
- `shoki task:list` — View open tasks in active sprint
- `shoki sprint board <id>` — Visual Kanban board
- `shoki vault audit` — Audit credential expiration health
- `shoki vault triage [query]` — Troubleshoot credential failures
- `shoki vault run -- pytest tests/` — Run tests with in-memory secrets
- `ctp "<message>"` — Atomic commit, tag, and push release
