#!/usr/bin/env python3
"""
CTP: Commit, Tag & Push CLI Extension
=====================================
A 1-line release execution pipeline for autonomous AI coding agents
and human software engineers.
"""

import os
import sys
import re
import argparse
import subprocess

def run_git(args, capture_output=False, check=True):
    try:
        res = subprocess.run(
            ["git"] + args,
            check=check,
            text=True,
            capture_output=capture_output
        )
        return res.stdout.strip() if capture_output else ""
    except subprocess.CalledProcessError as e:
        if not check:
            return ""
        print(f"Git error: {e}", file=sys.stderr)
        sys.exit(e.returncode)

def get_current_branch():
    return run_git(["branch", "--show-current"], capture_output=True, check=False) or "main"

def get_latest_tag():
    return run_git(["describe", "--tags", "--abbrev=0"], capture_output=True, check=False) or "v0.1.0"

def suggest_next_patch(tag):
    match = re.match(r"^v?(\d+)\.(\d+)\.(\d+)(.*)$", tag)
    if match:
        major, minor, patch, extra = match.groups()
        prefix = "v" if tag.startswith("v") else ""
        return f"{prefix}{major}.{minor}.{int(patch) + 1}"
    return f"{tag}.1"

def main():
    parser = argparse.ArgumentParser(
        prog="ctp",
        description="CTP: Atomic Commit, Tag & Push Release Command"
    )
    parser.add_argument("message", nargs="?", default=None, help="Commit message")
    parser.add_argument("tag", nargs="?", default=None, help="Tag name (e.g. v0.1.1)")
    parser.add_argument("-m", "--message-flag", dest="flag_msg", help="Commit message")
    parser.add_argument("-t", "--tag-flag", dest="flag_tag", help="Tag name")
    parser.add_argument("--no-tag", action="store_true", help="Skip creating a git tag")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without executing")

    args = parser.parse_args()

    # Commit message resolution
    commit_msg = args.flag_msg or args.message
    if not commit_msg:
        if sys.stdin.isatty():
            commit_msg = input("Enter commit message: ").strip()
        else:
            print("Error: Commit message required.", file=sys.stderr)
            sys.exit(1)

    if not commit_msg:
        print("Error: Commit message cannot be empty.", file=sys.stderr)
        sys.exit(1)

    branch = get_current_branch()
    latest_tag = get_latest_tag()
    target_tag = args.flag_tag or args.tag

    if not args.no_tag and not target_tag:
        target_tag = suggest_next_patch(latest_tag)

    print(f"\n🚀 CTP Release Pipeline (Branch: {branch})")
    print(f"   Commit Message : {commit_msg}")
    if args.no_tag:
        print("   Tagging        : SKIPPED (--no-tag)")
    else:
        print(f"   Target Tag     : {target_tag} (Latest: {latest_tag})")

    if args.dry_run:
        print("\n[Dry Run] Actions simulated successfully.")
        return

    # 1. Git Add
    print("\n1. Staging changes (git add -A)...")
    run_git(["add", "-A"])

    # 2. Git Commit
    print("2. Committing changes...")
    try:
        run_git(["commit", "-m", commit_msg])
    except Exception:
        print("   Notice: Nothing new to commit, continuing to tag/push.")

    # 3. Git Tag
    if not args.no_tag and target_tag:
        print(f"3. Creating annotated tag '{target_tag}'...")
        run_git(["tag", "-a", target_tag, "-m", f"Release {target_tag}: {commit_msg}"])

    # 4. Git Push
    print(f"4. Pushing to origin/{branch}...")
    run_git(["push", "origin", branch])

    if not args.no_tag and target_tag:
        print(f"   Pushing tag '{target_tag}'...")
        run_git(["push", "origin", target_tag])

    print("\n✓ CTP Release complete! Successfully committed, tagged, and pushed.\n")

if __name__ == "__main__":
    main()
