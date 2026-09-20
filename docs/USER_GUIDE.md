# Shokitora (書記虎) Comprehensive User Guide & Reference Manual

**Version:** 0.1.1  
**Author:** Vincent Capers Jr., Founder & Principal Architect  
**Corporate Entity:** VonCasper Solutions  
**License:** Dual MIT & Apache 2.0  

---

## 1. Introduction & Architectural Philosophy

Modern software engineering teams and autonomous AI coding agents face three distinct operational friction points:

1. **Context Fragmentation:** Engineering decisions, bug investigations, and rationale are scattered across Slack, Jira, PR comments, and fleeting memory. When an AI agent resets its context window or a new engineer joins, this context is completely lost.
2. **Secret Sprawl & Plaintext Leaks:** Plaintext `.env` files accidentally committed to Git repositories or backed up to unsecured cloud drives represent the single largest vector of developer credential compromise.
3. **Release Friction:** Shipping clean semantic patch releases requires manual Git commands (`git add`, `git commit`, `git tag`, `git push origin branch`, `git push origin tag`), leading to missed tags and inconsistent versions.

**Shokitora (書記虎)** resolves all three problems with a single, unified, local-first control plane:
- **Tiger Scribe:** A local SQLite-backed engineering memory ledger tracking **Tasks**, **Ideas**, **Decisions**, **Expenses**, and **Learnings**.
- **Sovereign Vault:** An air-gapped secrets engine cryptographically bound to the physical CPU and motherboard silicon of your workstation, featuring automatic credential expiration audits and failure triage.
- **Atomic CTP Pipeline:** A 1-line release automation tool that stages, commits, tags, and pushes in a single atomic operation.

---

## 2. The 5 Sovereign Memory Primitives

Shokitora organizes all engineering activity into 5 relational primitives stored in a local SQLite database (`journal.db`):

```
       [💡 IDEA]  ──(prompts)──>  [📋 TASK]
                                      │
              ┌───────────────────────┼───────────────────────┐
              ▼                       ▼                       ▼
       [⚖️ DECISION]             [💰 EXPENSE]            [🧠 LEARNING]
```

### 2.1 📋 Tasks (`task`) — *The Execution Engine*

Tasks represent discrete, verifiable units of engineering work. Unlike generic to-do lists, every Shokitora task enforces rigorous engineering hygiene:
- **Mandatory Sprint Binding:** A task cannot float unassigned; it must belong to an active sprint (`--sprint <id>`).
- **Success Criteria (Definition of Done):** An explicit, testable criteria required before the task can be marked completed (`--success "<criteria>"`).
- **Status State Machine:** Tasks transition through explicit states:
  `OPEN` $\rightarrow$ `IN_PROGRESS` $\rightarrow$ `COMPLETED` (or `BLOCKED`, `ARCHIVED`, `OBSOLETE`).
- **Audit History:** Every status transition is automatically recorded with an immutable timestamp in the `status_history` table, creating an audit-ready log for patent defense and R&D compliance.
- **Blockers:** Tasks can depend on other tasks (`--blocked-by <id>`).
- **Hours & Docs:** Track R&D hours (`--hours <N>`) and link to architectural design plans (`--doc <relative_path>`).

#### CLI Commands for Tasks
```bash
# Add a task to Sprint 1
shoki add task "Implement hardware key derivation" --sprint 1 \
  --success "Unit tests pass with 100% coverage" \
  --due 2026-09-26 \
  --doc docs/design/vault_derivation.md

# List active sprint tasks
shoki task:list

# Transition status to IN_PROGRESS
shoki update 1 --status IN_PROGRESS

# Complete task and log R&D hours
shoki update 1 --status COMPLETED --hours 3.5

# Inspect chronological state transitions (Audit Log)
shoki task:history 1
```

---

### 2.2 💡 Ideas (`idea`) — *The Conceptual Spark*

Ideas capture high-level concepts, architectural hypotheses, and market opportunities before they are scheduled into a sprint.
- **Zero Friction:** Can be logged instantly without requiring a sprint ID.
- **Ancestor Lineage:** Ideas serve as the root parent (`parent_id`) for downstream tasks, decisions, and experiments.
- **Prevents Idea Graveyards:** Queryable at any time via `shoki ideas:list`.

#### CLI Commands for Ideas
```bash
# Record an architectural idea
shoki add idea "Evaluate HKDF-SHA256 vs PBKDF2 for CPU hardware fingerprint key derivation"

# List all open ideas
shoki ideas:list

# Convert idea #42 into execution by linking a new task to it
shoki add task "Benchmark HKDF-SHA256 key derivation" --sprint 1 \
  --parent 42 --success "Latency under 5ms"
```

---

### 2.3 ⚖️ Decisions (`decision`) — *Architectural & Governance Memory*

Decisions record permanent Architectural Decision Records (ADRs). They answer the most critical question in software engineering: **"Why did we build it this way?"**
- **Eliminates Circular Debates:** Prevents teams and AI agents from re-debating settled architectural choices months later.
- **Captures Rejected Alternatives:** Explicitly documents which alternative designs were considered and why they were rejected.
- **Defensible Intellectual Property:** Provides contemporaneous evidence of invention dates and architectural intent for patent prosecution.

#### CLI Commands for Decisions
```bash
# Record an architectural decision
shoki add decision "Adopt AES-256-GCM authenticated encryption for Sovereign Vault" \
  --parent 1

# Record a technical choice with alternatives documented
shoki add decision "Select SQLite WAL mode over client-server PostgreSQL for zero-dependency local ledger"
```

---

### 2.4 💰 Expenses (`expense`) — *Runway & Financial Hygiene*

Expenses track direct costs incurred during research, prototyping, and operations.
- **Granular Accounting:** Records `amount` and `currency` (default: `USD`) associated with an explicit task or sprint.
- **Categories:** Cloud GPU compute, domain purchases, hardware appliances, patent filing fees, API usage.
- **R&D Tax Credit Compliance:** Matches financial outlays directly to specific engineering task IDs, creating clean audit trails for IRS R&D tax credit deductions.
- **Sprint Rollups:** Automatically calculates total sprint expenditures (`shoki sprint:expenses`).

#### CLI Commands for Expenses
```bash
# Record an expense for a task
shoki add expense "NVIDIA RTX 5000 Ada Workstation GPU for on-premise inference" \
  --amount 4200.00 --currency USD --parent 1

# Record domain registration expense
shoki add expense "voncasper.com domain registration (Namecheap)" \
  --amount 14.58 --currency USD

# View sprint expense summary
shoki sprint:expenses 1
```

---

### 2.5 🧠 Learnings (`learning`) — *The Post-Mortem & Knowledge Graph*

Learnings capture hard-won empirical discoveries, obscure edge cases, vendor API quirks, and debugging post-mortems.
- **Anti-Regression Safeguard:** Prevents human developers and autonomous AI agents from repeating the same mistake across different sessions.
- **Context Injection:** When an AI agent begins a task, querying recent learnings prevents hallucinated solutions that have already failed.
- **Git Commit Analysis:** Automatically parsed from commit messages when using Scribe Git hooks.

#### CLI Commands for Learnings
```bash
# Log a debugging discovery
shoki add learning "macOS IOPlatformUUID requires root permissions on macOS 14+; fallback to ioreg ensures unprivileged reads" \
  --parent 1

# Log an API rate-limit discovery
shoki add learning "GitHub REST API enforces a strict secondary rate limit of 100 concurrent requests; serialize batch calls with 50ms jitter"
```

---

### 2.6 Relational Lineage: Connecting the Primitives

The true power of Shokitora emerges when primitives are linked hierarchically using `shoki link <child_id> <parent_id>`. 

Consider this complete engineering lifecycle:
1. An **Idea** (`#10`) is recorded: *"Eliminate plaintext .env secrets."*
2. A **Task** (`#11`) is scheduled in Sprint 1: *"Build CPU-bound Sovereign Vault"* (Parent: `#10`).
3. A **Decision** (`#12`) is recorded: *"Derive key via HKDF using /etc/machine-id and DMI UUID"* (Parent: `#11`).
4. An **Expense** (`#13`) is incurred: *"Dell Precision 5860 test unit - $3,200.00"* (Parent: `#11`).
5. A **Learning** (`#14`) is discovered: *"Virtual machine DMI UUIDs can collide; add /proc/cpuinfo salt"* (Parent: `#11`).

When you query `shoki task:list`, Shokitora renders the entire tree:
```
#11 [2026-09-20] TASK [IN_PROGRESS]: Build CPU-bound Sovereign Vault [Sprint: Sprint 1]
    ├── Doc: docs/design/vault_spec.md
    ├── Success Criteria: 100% unit test pass rate on Linux, macOS, and Windows
    └── Children: #12 DECISION, #13 EXPENSE, #14 LEARNING
```

---

## 3. Sprint Cadence & Terminal Kanban

Shokitora structures time into sprints with explicit goals and parent lineage.

### 3.1 Managing Sprints
```bash
# Create a new sprint
shoki sprint add "Sprint 1" --start 2026-09-20 --end 2026-09-26 \
  --goal "Ship Shokitora v0.1.1 with Sovereign Vault Expiry Engine"

# List all sprints (newest first)
shoki sprint:list

# Update sprint status
shoki sprint update 1 --status ACTIVE
```

### 3.2 Visual Terminal Kanban Board
Shokitora includes a built-in terminal Kanban board that renders live sprint tasks in column format:
```bash
shoki sprint board 1
```

Output:
```
🐯 KANBAN BOARD: Sprint 1
Goal: Ship Shokitora v0.1.1 with Sovereign Vault Expiry Engine
⏱️ Total Hours Logged in Sprint: 4.5h

BACKLOG (OPEN)             | ACTIVE (IN_PROGRESS)       | DONE (COMPLETED)
---------------------------------------------------------------------------------------------
#3 Add Windows wmic probe  | #1 (3.0h) Implement Vault  | #2 (1.5h) Setup PyPI packaging
                           | [!] Blocked by #4          |
```

---

## 4. Sovereign Vault & The Expiration Engine (v0.1.1)

The **Sovereign Vault** is a zero-cloud, hardware-bound local secrets manager. It completely eliminates plaintext `.env` files and prevents API credentials from leaking into Git repositories.

### 4.1 Hardware Silicon Binding
When the vault initializes, it reads the physical identity of your computer:
- **Linux:** `/etc/machine-id`, DMI System UUID, `/proc/cpuinfo`.
- **macOS:** `IOPlatformUUID` via `ioreg`, `sysctl machdep.cpu`.
- **Windows:** Motherboard UUID via CIM/wmic, Processor ID.

The hardware fingerprint is hashed via **HKDF-SHA256** to derive a 256-bit AES-GCM encryption key. If `.scribe_vault.enc` is stolen, copied, or pushed to GitHub, **it cannot be decrypted on any other computer.**

```bash
# Verify your hardware silicon lock
shoki vault status
```

---

### 4.2 Eliminating Plaintext `.env` Files
Import all variables from an existing `.env` file into the encrypted vault and securely shred the plaintext source:
```bash
shoki vault import-env .env --delete-source
```
*The shredder overwrites the `.env` file with zeros on disk before deleting it.*

### 4.3 In-Memory Secret Injection (`run`)
Execute any script, server, or test suite with secrets injected purely into in-memory RAM environment variables (`os.environ`), leaving zero footprint on disk:
```bash
shoki vault run -- python3 my_agent.py
shoki vault run -- pytest tests/
shoki vault run -- npm start
```

---

### 4.4 Expiration Policies (`--expires-in` / `--expires`) — *New in v0.1.1*

Third-party developer credentials (like GitHub Personal Access Tokens) frequently carry mandatory expiration windows (e.g., 90 days). The Sovereign Vault allows recording and enforcing expiration metadata.

#### Supported Expiration Formats
- **Relative Durations (`--expires-in`):**
  - `90d` (90 days)
  - `30d` (30 days)
  - `48h` (48 hours)
  - `12m` or `12mo` (12 months)
  - `1y` (1 year)
  - Integer days (e.g., `90`)
- **Absolute Dates (`--expires`):**
  - `YYYY-MM-DD` (sets expiration to `23:59:59 UTC` of that day)
  - ISO-8601 UTC string (`2026-12-19T15:00:00Z`)
- **Clearing Expiration Policy:**
  - `--expires CLEAR` or `--expires NONE` restores perpetual status.

#### Storing Secrets with Expiration
```bash
# Store a new GitHub PAT with a 90-day expiration window
shoki vault set github/token "ghp_..." --desc "GitHub Personal Access Token" --expires-in 90d

# Store an OpenAI key expiring on a specific date
shoki vault set openai/api_key "sk-..." --expires 2026-12-31
```

#### Metadata-Only Updates (Preserving Secret Values)
To update the expiration date or description of an existing secret without re-entering the secret value:
```bash
# Updates expiration to 90 days from today while preserving the decrypted secret!
shoki vault set github/token --expires-in 90d

# Clear the expiration policy to make the secret perpetual
shoki vault set github/token --expires CLEAR
```

---

### 4.5 Security & Posture Audit (`shoki vault audit`) — *New in v0.1.1*

Audit all stored credentials across your workstation to identify upcoming expiration deadlines and stale keys before an outage occurs:
```bash
shoki vault audit
```

Output:
```
================================================================================
 SCRIBE VAULT AUDIT - POSTURE & EXPIRATION REPORT
================================================================================
Overall Health   : HEALTHY
Total Secrets    : 5
  - Expired      : 0
  - Expiring Soon: 0 (within 14 days)
  - Active       : 1
  - Perpetual    : 4
--------------------------------------------------------------------------------

AUDITED SECRETS INVENTORY:
KEY                          | PREVIEW        | STATUS        | EXPIRES                | DESCRIPTION
-------------------------------------------------------------------------------------------------------------------
corporate/ein                | ******9473     | PERPETUAL     | No Expiry              | Employer Identification Number
github/token                 | ********7ysk   | ACTIVE        | 89d left (Dec 19)      | GitHub PAT for voncasper
journal_web_ui/password      | *******@716    | PERPETUAL     | No Expiry              | Admin Password

Status: HEALTHY
```

#### Status Classification
- `PERPETUAL`: No expiration configured.
- `ACTIVE`: Key is valid with >14 days remaining.
- `EXPIRING_SOON`: Key expires within warning threshold (default: 14 days; customize with `--warn-days <N>`).
- `EXPIRED`: Key expiration has passed (`CRITICAL` overall health alert).

For CI/CD and pre-commit automation, export audit results as raw JSON:
```bash
shoki vault audit --json
```

---

### 4.6 Troubleshooting & Failure Triage Assistant (`shoki vault triage`) — *New in v0.1.1*

When an API call, deployment script, or git push fails with `HTTP 401 Bad credentials` or `Unauthorized`, the **Triage Assistant** immediately diagnoses whether an expired token is the root cause:

```bash
# Triage a specific provider
shoki vault triage github

# Or triage all stored credentials
shoki vault triage
```

Output:
```
================================================================================
 SCRIBE VAULT TRIAGE & DIAGNOSTIC ASSISTANT (Filter: 'github')
================================================================================

[✓] Secret: github/token
    Status      : ACTIVE (89d left (Dec 19))
    Diagnosis   : OK: Secret is active (89 days remaining).
    Service     : GitHub
    Renew URL   : https://github.com/settings/tokens
    Action      : Generate a new token with required scopes ('repo', 'workflow', etc.) and run: scribe vault set github/token <new_token> --expires-in 90d

================================================================================
```

If the token is expired, Triage flags it in red, diagnoses the exact failure, and provides the direct URL to generate a replacement token.

---

### 4.7 Migration Bundles Across Laptops

When upgrading your computer, export a passphrase-encrypted bundle:
```bash
# On old computer: Export with master recovery passphrase (PBKDF2 600k rounds)
shoki vault export-bundle my_backup.bundle.json

# On new computer: Import and immediately re-lock to new computer's CPU silicon
shoki vault import-bundle my_backup.bundle.json
```

---

## 5. Atomic CTP Release Pipeline (`ctp`)

Shipping semantic releases manually is error-prone. The `ctp` (**Commit, Tag, Push**) pipeline executes the entire release process in a single atomic command:

```bash
ctp "feat(vault): add optional expiration metadata, audit posture, and triage assistant"
```

### What CTP Automates
1. **Stages all modified and untracked files:** `git add -A`
2. **Commits with conventional message:** `git commit -m "<message>"`
3. **Calculates next semantic patch version:** Reads latest tag (e.g. `v0.1.0`), increments patch to `v0.1.1`.
4. **Creates annotated Git tag:** `git tag -a v0.1.1 -m "Release v0.1.1: ..."`
5. **Pushes branch and tag atomically:** `git push origin main && git push origin v0.1.1`

#### Explicit Tagging and Options
```bash
# Specify explicit version tag
ctp "chore: major release" v1.0.0

# Skip tag creation (commit and push only)
ctp "docs: update user guide" --no-tag

# Simulate actions without executing
ctp "feat: experimental release" --dry-run
```

---

## 6. Python SDK Programmatic Reference

You can access Shokitora's ledger and vault directly in your Python applications and AI agent loops:

```python
from shokitora import (
    # Secrets Management
    get_secret,
    set_secret,
    list_secrets,
    audit_secrets,
    triage_secrets,
    load_secrets_into_environ,
    # Expiry Helpers
    parse_expiry,
    compute_expiry_metadata,
)

# 1. Retrieve a decrypted secret in memory
api_key = get_secret("github/token")

# 2. Store a secret with a 90-day expiration
set_secret(
    key="huggingface/token",
    value="hf_...",
    description="Hugging Face Hub Write Token",
    expires_at=parse_expiry(expires_in="90d")
)

# 3. Load all vault secrets into os.environ at startup
load_secrets_into_environ()

# 4. Programmatic Security Audit
audit_report = audit_secrets(warn_days=14)
if audit_report["health"] == "CRITICAL":
    print("ALERT: One or more credentials have expired!")
    for item in audit_report["expired"]:
        print(f"Expired key: {item['key']} -> Renew at {item['remediation_url']}")

# 5. Programmatic Triage
diagnosis = triage_secrets(query="github")
print(diagnosis[0]["diagnosis"])
```

---

## 7. Autonomous AI Agent Integration Patterns

Autonomous AI coding agents (such as Google Antigravity, Hermes, Claude Code, or custom LangChain/AutoGen loops) excel when grounded by Shokitora's memory ledger:

### 7.1 Pre-Task Grounding Routine
Before an agent executes code, prompt it to query recent context:
```bash
# Agent inspects current sprint tasks and goals
shoki task:list

# Agent checks recent architectural decisions to prevent violating design patterns
shoki list --category decision --limit 5

# Agent checks recent learnings to avoid known bugs
shoki list --category learning --limit 5
```

### 7.2 Post-Task Logging Routine
Upon completing a coding objective, the agent records its output:
```bash
# Complete task and record actual hours
shoki update <id> --status COMPLETED --hours 1.2

# If the agent made an architectural trade-off, log a decision
shoki add decision "Used HKDF over PBKDF2 for derivation speed" --parent <id>

# If the agent hit a vendor edge case, log a learning
shoki add learning "PyPI rejected package due to uppercase letters in name" --parent <id>
```

---

## 8. Summary Command Cheat Sheet

| Command | Description |
|---|---|
| `shoki init` | Initialize local SQLite journal database (`journal.db`) |
| `shoki add task "<desc>" --sprint <id>` | Add a task with success criteria and due date |
| `shoki task:list` | List open tasks in the active sprint |
| `shoki update <id> --status <status>` | Transition task status (`IN_PROGRESS`, `COMPLETED`) |
| `shoki task:history <id>` | View full chronological audit history for a task |
| `shoki sprint board <id>` | Render visual interactive terminal Kanban board |
| `shoki add idea "<desc>"` | Record conceptual ideas and feature sparks |
| `shoki add decision "<desc>"` | Record Architecture Decision Records (ADRs) |
| `shoki add expense "<desc>" --amount <N>` | Log project and R&D expenses |
| `shoki add learning "<desc>"` | Record bug discoveries and post-mortems |
| `shoki link <child_id> <parent_id>` | Connect entries into a relational parent-child tree |
| `shoki vault status` | Check host CPU silicon hardware cryptographic binding |
| `shoki vault set <key> <val> --expires-in 90d` | Store secret with relative expiration |
| `shoki vault set <key> --expires-in 90d` | Update expiration metadata preserving existing secret |
| `shoki vault audit` | Audit all credentials for expiration and posture |
| `shoki vault triage [query]` | Diagnose authentication failures and get renewal URLs |
| `shoki vault import-env .env --delete-source` | Import and securely shred plaintext `.env` file |
| `shoki vault run -- <command>` | Run command with secrets injected in-memory |
| `ctp "<commit_message>"` | Atomic 1-line release: stage, commit, tag, and push |
