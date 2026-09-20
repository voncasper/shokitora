#!/usr/bin/env python3
"""
Shokitora (書記虎) Unified Master CLI Router
============================================
Dispatches to:
- `vault`: Scribe CPU-bound local secrets manager
- `ctp`: Atomic Commit, Tag & Push release automation
- `journal`: SQLite technical memory & audit ledger (task, sprint, decision, learning)
"""

import sys
import os

from shokitora import __version__

def print_help():
    print(f"""
🐯 Shokitora (書記虎) v{__version__} - The Sovereign Tiger Scribe
A local-first engineering governance, secrets, and release control plane.

Usage:
  shoki <command> [options]
  shokitora <command> [options]
  scribe <command> [options]

Subsystems:
  vault          CPU-bound zero-cloud secrets manager (.env eliminator)
  hooks          Git hooks manager (pre-commit secret guard & post-commit ledger)
  skill          Universal agent skills installer (Antigravity, Claude, Cursor, Windsurf)
  ctp            Atomic 1-line release pipeline (Commit -> Tag -> Push)
  init           Initialize local SQLite journal database
  task:list      List tasks in active sprint
  sprint:list    List all sprints
  ideas:list     List all recorded ideas
  task:history   Show audit transition history for a task
  add            Add journal entry (task, decision, learning, idea, expense)
  update         Update task or entry status
  link           Link child entry to parent entry
  sprint         Sprint management (add, update, list, board)

Examples:
  shoki skill install all
  shoki hooks install
  shoki vault status
  shoki vault import-env .env --delete-source
  shoki vault run -- python app.py
  shoki task:list
  shoki ctp "feat: implement local vault" v0.1.0
""")

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ["-h", "--help", "help"]:
        print_help()
        sys.exit(0)

    if sys.argv[1] in ["-v", "--version", "version"]:
        print(f"Shokitora (書記虎) v{__version__}")
        sys.exit(0)

    cmd = sys.argv[1]

    # Route 'skill' subcommand
    if cmd in ["skill", "skill:install", "skill:status", "skill:list", "skills"]:
        sys.argv.pop(1)
        if cmd == "skill:install":
            sys.argv.insert(1, "install")
        elif cmd == "skill:status":
            sys.argv.insert(1, "status")
        elif cmd == "skill:list":
            sys.argv.insert(1, "list")
        from shokitora.cli.commands_skill import main as skill_main
        skill_main()
        return

    # Route 'hooks' subcommand
    if cmd in ["hooks", "hooks:install", "hooks:status"]:
        sys.argv.pop(1)
        if cmd == "hooks:install":
            sys.argv.insert(1, "install")
        elif cmd == "hooks:status":
            sys.argv.insert(1, "status")
        from shokitora.cli.commands_hooks import main as hooks_main
        hooks_main()
        return

    # Route 'vault' subcommand
    if cmd == "vault":
        sys.argv.pop(1)
        from shokitora.core.vault import main as vault_main
        vault_main()
        return

    # Route 'ctp' subcommand
    if cmd == "ctp":
        sys.argv.pop(1)
        from shokitora.cli.commands_ctp import main as ctp_main
        ctp_main()
        return

    # Route journal commands to journal_db.py
    from shokitora.core.journal_db import main as journal_main
    sys.argv.pop(0)  # remove program name, keeping the subcommand as argv[0]
    journal_main()

if __name__ == "__main__":
    main()
