---
name: shokitora
description: Sovereign Tiger Scribe engineering ledger (tasks, ideas, decisions, expenses, learnings) and CPU-bound hardware secrets vault.
---

# Shokitora (書記虎) Agent Skill

You are pair programming with a human engineer in a repository governed by **Shokitora**. Shokitora provides persistent engineering memory, an immutable technical ledger, and an air-gapped secrets manager bound to host workstation CPU silicon.

## Core Directives for Autonomous AI Agents

1. **Pre-Task Memory Grounding Routine:**
   - Inspect open sprint tasks and criteria: `shoki task:list`
   - Review recent architectural decisions to ensure you do not violate established design patterns: `shoki list --category decision --limit 5`
   - Review recent learnings to prevent repeating known bugs or edge cases: `shoki list --category learning --limit 5`

2. **Strict Zero Plaintext Secrets Policy:**
   - NEVER create, edit, or commit plaintext `.env` files.
   - NEVER print raw API tokens or credentials into transcripts, comments, or logs.
   - Retrieve credentials dynamically in memory: `shoki vault get <key>` or execute commands via in-memory injection: `shoki vault run -- <cmd>`.
   - When adding third-party API credentials, record expiration: `shoki vault set <key> <val> --expires-in 90d`.
   - If an API or Git push returns HTTP 401 Unauthorized, diagnose immediately via: `shoki vault triage [service]`.

3. **Post-Task Documentation Routine:**
   - When completing an engineering objective, update status and log hours: `shoki update <task_id> --status COMPLETED --hours <N>`
   - If an architectural trade-off or package integration was decided, record a decision: `shoki add decision "<rationale>" --parent <task_id>`
   - If a bug resolution, hardware quirk, or vendor limitation was discovered, record a learning: `shoki add learning "<discovery>" --parent <task_id>`

## Quick Reference Commands

| Command | Purpose |
|---|---|
| `shoki task:list` | View open tasks in active sprint |
| `shoki sprint board <id>` | Render visual terminal Kanban board |
| `shoki add task "<desc>" --sprint <id>` | Schedule a task with success criteria |
| `shoki update <id> --status <status>` | Transition status (`IN_PROGRESS`, `COMPLETED`) |
| `shoki task:history <id>` | View state transition audit history |
| `shoki add decision "<desc>" --parent <id>` | Record Architecture Decision Record (ADR) |
| `shoki add learning "<desc>" --parent <id>` | Record technical discovery or post-mortem |
| `shoki vault status` | Verify CPU silicon cryptographic binding |
| `shoki vault audit` | Audit all credentials for expiration posture |
| `shoki vault triage [query]` | Diagnose auth failures and get renewal URLs |
| `shoki vault run -- <command>` | Execute process with RAM-only secret injection |
| `ctp "<message>"` | Atomic 1-line release (stage, commit, tag, push) |
