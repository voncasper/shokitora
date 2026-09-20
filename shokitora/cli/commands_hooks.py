#!/usr/bin/env python3
"""
Shokitora Git Hooks CLI Manager
===============================
Automates installation and status checking of Shokitora's Git hooks:
- `pre-commit`: Blocks commits containing plaintext .env files or raw API tokens.
- `post-commit`: Automatically logs commits, decisions, and task linkages to the SQLite ledger.
"""

import os
import sys
import stat
import subprocess
import argparse

HOOKS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")


def get_git_hooks_dir():
    try:
        git_dir = subprocess.check_output(
            ["git", "rev-parse", "--git-dir"],
            stderr=subprocess.DEVNULL,
            text=True
        ).strip()
        return os.path.join(git_dir, "hooks")
    except Exception:
        return None


def install_hooks(force=False):
    target_hooks_dir = get_git_hooks_dir()
    if not target_hooks_dir:
        print("Error: Not a git repository. Run this inside your git project directory.", file=sys.stderr)
        sys.exit(1)

    os.makedirs(target_hooks_dir, exist_ok=True)
    hooks_to_install = [
        ("pre-commit", "pre_commit_hook.sh"),
        ("post-commit", "post_commit_hook.sh")
    ]

    installed = []
    for hook_name, script_name in hooks_to_install:
        source_path = os.path.join(HOOKS_DIR, script_name)
        target_path = os.path.join(target_hooks_dir, hook_name)

        if not os.path.exists(source_path):
            print(f"Warning: Source hook '{script_name}' not found at {source_path}", file=sys.stderr)
            continue

        with open(source_path, "r", encoding="utf-8") as sf:
            content = sf.read()

        with open(target_path, "w", encoding="utf-8") as tf:
            tf.write(content)

        # Make executable
        st = os.stat(target_path)
        os.chmod(target_path, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        installed.append(hook_name)

    print("\n🐯 Shokitora Git Hooks Installed Successfully!")
    print("=" * 60)
    for h in installed:
        print(f"  ✓ .git/hooks/{h}")
    print("\nProtections Active:")
    print("  • pre-commit  : Prevents committing plaintext .env files & raw tokens")
    print("  • post-commit : Automatically logs commits into Shokitora technical ledger\n")


def status_hooks():
    target_hooks_dir = get_git_hooks_dir()
    if not target_hooks_dir:
        print("Error: Not a git repository.", file=sys.stderr)
        sys.exit(1)

    print("\n🐯 Shokitora Git Hooks Status")
    print("=" * 60)
    for hook_name in ["pre-commit", "post-commit"]:
        hook_path = os.path.join(target_hooks_dir, hook_name)
        if os.path.exists(hook_path):
            is_exec = os.access(hook_path, os.X_OK)
            status_label = "ACTIVE (Executable)" if is_exec else "INSTALLED (Not Executable)"
            print(f"  • {hook_name:<14} : {status_label}")
        else:
            print(f"  • {hook_name:<14} : NOT INSTALLED")
    print("")


def uninstall_hooks():
    target_hooks_dir = get_git_hooks_dir()
    if not target_hooks_dir:
        print("Error: Not a git repository.", file=sys.stderr)
        sys.exit(1)

    removed = []
    for hook_name in ["pre-commit", "post-commit"]:
        hook_path = os.path.join(target_hooks_dir, hook_name)
        if os.path.exists(hook_path):
            os.remove(hook_path)
            removed.append(hook_name)

    if removed:
        print(f"✓ Removed Shokitora hooks: {', '.join(removed)}")
    else:
        print("No Shokitora hooks found to remove.")


def main():
    parser = argparse.ArgumentParser(
        prog="shoki hooks",
        description="Shokitora Git Hooks Manager (pre-commit guardrails & post-commit logging)"
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    p_inst = subparsers.add_parser("install", help="Install Shokitora pre-commit and post-commit hooks")
    p_inst.add_argument("--force", action="store_true", help="Overwrite existing hooks")

    subparsers.add_parser("status", help="Check status of installed Git hooks")
    subparsers.add_parser("uninstall", help="Remove Shokitora Git hooks")

    args = parser.parse_args()

    if args.subcommand == "install":
        install_hooks(force=args.force)
    elif args.subcommand == "status":
        status_hooks()
    elif args.subcommand == "uninstall":
        uninstall_hooks()


if __name__ == "__main__":
    main()
