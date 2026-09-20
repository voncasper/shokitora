# Shokitora (書記虎) — The Sovereign Tiger Scribe

<p align="center">
  <strong>The Git-Native Memory Ledger, CPU-Bound Sovereign Vault, and Atomic CTP Release Control Plane for AI Coding Agents and Software Engineers.</strong>
</p>

<p align="center">
  <a href="https://github.com/voncasper/shokitora/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT%20%2F%20Apache%202.0-blue.svg" alt="License"></a>
  <a href="https://pypi.org/project/shokitora/"><img src="https://img.shields.io/badge/Python-3.9%2B-green.svg" alt="Python Version"></a>
  <img src="https://img.shields.io/badge/Sovereignty-100%25%20Local%20%26%20Zero%20Cloud-orange.svg" alt="Zero Cloud">
  <img src="https://img.shields.io/badge/Cryptography-AES--256--GCM%20%2B%20HKDF-purple.svg" alt="Cryptography">
</p>

---

## 🐯 Lore & Vision

Rooted in the ancient lore of the **Tiger Tally (虎符 - Torafu)** — the sovereign split-seal bronze talisman used by generals to authenticate decrees and mobilize forces — **Shokitora (書記虎)** (*derived from Japanese **Shoki (書記)** for Scribe/Chronicler and **Tora (虎)** for Tiger*) brings ironclad memory, zero-cloud secret security, and atomic release governance to autonomous AI coding agents (Claude Code, Antigravity, Cursor, Devin, Hermes) and human developers.

In modern agentic pair programming, autonomous coding agents suffer from three major points of friction:
1. **Context Amnesia:** Decisions and architectural breakthroughs vanish when conversation windows reset.
2. **Plaintext `.env` Leakage:** Developers constantly risk leaking high-stakes API keys (`GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `GITHUB_TOKEN`) to public GitHub repos.
3. **Manual Release Drudgery:** Multi-step `git add`, `git commit`, `git tag`, and `git push` routines slow down autonomous velocity.

**Shokitora solves all three in a single, 100% local, pure-Python control plane.**

---

## 🚀 The 4 Core Pillars

```
+-------------------------------------------------------------------------------+
|                         SHOKITORA AGENTIC CONTROL PLANE                       |
+-------------------------------------------------------------------------------+
        |                       |                       |               |
        v                       v                       v               v
+----------------+      +----------------+      +---------------+ +---------------+
|  TIGER SCRIBE  |      |   CPU VAULT    |      |  CTP RELEASE  | | AUDIT REPORTS |
| (Memory Ledger)|      | (Secrets Mgmt) |      | (1-Line Ship) | |  (Governance) |
+----------------+      +----------------+      +---------------+ +---------------+
| • SQLite       |      | • HKDF-SHA256  |      | • Git Commit  | | • Compliance  |
| • Git Hooks    |      | • AES-256-GCM  |      | • Auto Tag    | | • History     |
| • Tasks/Sprint |      | • .env Shred   |      | • Git Push    | | • R&D Credits |
+----------------+      +----------------+      +---------------+ +---------------+
```

### 1. 📝 Passive Technical Memory & IP Ledger (`shoki task`, `shoki sprint`)
- **Automated Post-Commit Ledger:** Every `git commit` triggers an automated analysis logging decisions and learnings into a local SQLite database (`journal.db`).
- **Audit-Ready History:** Chronological state transitions (`OPEN` $\rightarrow$ `IN_PROGRESS` $\rightarrow$ `COMPLETED`) preserved forever for patent disclosures and engineering audits.
- **Visual Sprint Board:** Terminal Kanban boards (`shoki sprint board <id>`) with hours tracking.

### 2. 🔒 CPU-Bound Sovereign Vault (`shoki vault`)
- **Silicon Hardware Binding:** Derives a 256-bit AES key via **HKDF-SHA256** directly from the local developer workstation's CPU and machine identity (`/etc/machine-id` on Linux, `IOPlatformUUID` on macOS, and BIOS UUID on Windows).
- **Plaintext `.env` Elimination:**
  - `shoki vault import-env .env --delete-source`: Imports variables and cryptographically shreds the plaintext file.
  - `shoki vault run -- <cmd>`: Decrypts secrets purely in RAM and injects them into child process `os.environ`. **No plaintext secrets ever touch disk.**
- **Zero-Prompt Local Decryption:** Instant CLI and Python SDK queries without master passwords on your machine. Mathematically uncrackable if the encrypted file is copied off-device.
- **Migration Bundles:** Password-encrypted bundles (PBKDF2-HMAC-SHA256, 600,000 rounds) for transferring secrets when upgrading laptops.

### 3. ⚡ Atomic CTP Release Pipeline (`ctp`)
- **One-Line Shipping:** Replaces multi-step manual release routines with a single command:
  ```bash
  ctp "feat: implement local secrets vault" v0.1.0
  ```
- Automatically stages changes, creates commit, calculates next semantic patch version (`v0.1.0` $\rightarrow$ `v0.1.1`), tags commit, and pushes both branch and tag to remote.

### 4. 📊 Corporate Reporting & Governance
- Automated Markdown and JSON exports of project milestones, strategic decisions, and logged R&D hours for team syncs and corporate record-keeping.

---

## 📦 Installation

Install via PyPI:
```bash
pip install shokitora
```

Or install locally from source:
```bash
git clone https://github.com/voncasper/shokitora.git
cd shokitora
pip install -e .
```

---

## 📚 Documentation & Guides

For complete architecture breakdowns, workflows, and advanced usage, explore the dedicated guides:
- **[Comprehensive User Guide](docs/USER_GUIDE.md)**: Deep dive into the **5 Sovereign Memory Primitives** (Tasks, Ideas, Decisions, Expenses, Learnings), Expiration Policies, Audit Reports, Failure Triage, and Python SDK.
- **[Git Hooks Setup & Automation Guide](docs/GIT_HOOKS_GUIDE.md)**: Step-by-step guide to installing local `pre-commit` secret leak guardrails and automatic `post-commit` technical journaling.

---

## 🛠️ Quickstart & Command Reference

Shokitora installs the command-line binaries `shoki`, `shokitora`, `scribe`, and `ctp`.

### 1. Initialize Database & Install Git Hooks
```bash
# Initialize local SQLite technical memory database
shoki init

# Install pre-commit guardrail (zero-leak filter) and post-commit journaling hook
shoki hooks install
```

### 2. Manage Tasks & Sprints
```bash
# Add a sprint
shoki sprint add "Sprint 1" --start 2026-09-20 --end 2026-09-26 --goal "Ship Shokitora v0.1.1"

# Add a task to the active sprint
shoki add task "Implement Hardware Vault" --sprint 1 --success "All unit tests pass"

# List active sprint tasks
shoki task:list

# Update task status and log work hours
shoki update 1 --status IN_PROGRESS
shoki update 1 --status COMPLETED --hours 2.5

# View visual terminal Kanban board
shoki sprint board 1
```

### 3. Manage Hardware-Bound Secrets (Eliminate Plaintext `.env`)
```bash
# Check host CPU silicon binding
shoki vault status

# Store a secret securely with optional expiration policy (e.g., 90-day GitHub PAT)
shoki vault set GITHUB_TOKEN "ghp_..." --desc "GitHub PAT" --expires-in 90d

# Update expiration or metadata on existing secret without re-entering the secret
shoki vault set GITHUB_TOKEN --expires-in 90d

# Audit all credentials for expiration posture and upcoming renewal deadlines
shoki vault audit

# Triage authentication failures or check specific token health
shoki vault triage github

# Retrieve secret value
shoki vault get GEMINI_API_KEY

# Import existing .env and securely shred plaintext file
shoki vault import-env .env --delete-source

# Run any application with in-memory secret injection (Zero disk footprint!)
shoki vault run -- python3 my_agent.py
shoki vault run -- pytest tests/

# Export migratable bundle when getting a new computer
shoki vault export-bundle my_backup.bundle.json
```

### 4. Ship Releases with 1-Line CTP
```bash
# Commit, tag, and push in one command
ctp "feat(vault): add hardware-bound CPU secret engine"

# Specify explicit release tag
ctp -m "chore: release initial public beta" -t "v0.1.0"
```

### 5. Multi-Agent Skills Setup (Universal Agent Interoperability)
```bash
# List supported agent platforms
shoki skill list

# Install drop-in skills and rules for all agents in 1 line
shoki skill install all

# Or install for a specific agent
shoki skill install antigravity   # Configures .gemini/skills/shokitora/SKILL.md
shoki skill install claude        # Configures CLAUDE.md
shoki skill install cursor        # Configures .cursorrules
shoki skill install windsurf      # Configures .windsurfrules

# Check status of installed agent skills
shoki skill status
```

---

## 🐍 Python SDK Usage

Access your sovereign vault and memory ledger directly from Python applications and autonomous agent loops:

```python
from shokitora import get_secret, load_secrets_into_environ

# 1. Retrieve individual decrypted secret
api_key = get_secret("GEMINI_API_KEY")

# 2. Or inject all vault secrets into os.environ in memory at startup
load_secrets_into_environ()

import os
print("Gemini API Key loaded:", os.getenv("GEMINI_API_KEY")[:8] + "...")
```

---

## 🛡️ Security & Multi-User Threat Model

Scribe Vault operates under a two-layer security model:
1. **Perimeter 1: Off-Host Protection (Silicon Hardware Lock):** Secrets are bound via HKDF-SHA256 to your physical CPU/system board. If `.scribe_vault.enc` is stolen, backed up to the cloud, or pushed to GitHub, it cannot be decrypted on any other computer.
2. **Perimeter 2: On-Host Co-Tenancy (POSIX File Permissions):** On a multi-user machine, isolation between accounts relies on strict POSIX mode `0600` (`-rw-------`). Standard users cannot access another user's vault.

---

## 📄 License

Shokitora is dual-licensed under:
- **MIT License** ([`LICENSE`](LICENSE))
- **Apache License 2.0** ([`LICENSE`](LICENSE))

Copyright © 2026 **VonCasper Solutions** (Vincent Capers Jr.).
All trademarks and brand assets are the property of VonCasper Solutions.
