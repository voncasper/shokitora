#!/usr/bin/env python3
"""
Shokitora Universal Agent Skill Installer & Manager
===================================================
Automates installation of drop-in skill files and guidelines for autonomous
AI coding agents:
- Google Antigravity (AGY / Gemini CLI): `.gemini/skills/shokitora/SKILL.md`
- Anthropic Claude Code: `CLAUDE.md`
- Cursor IDE: `.cursorrules`
- Windsurf Cascade: `.windsurfrules`
"""

import os
import sys
import shutil
import argparse

# Check package-internal skills directory first (when installed via pip), then repo root
_PKG_SKILLS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skills")
_REPO_SKILLS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "skills")
SKILLS_SOURCE_DIR = _PKG_SKILLS if os.path.isdir(_PKG_SKILLS) else _REPO_SKILLS


AGENTS = {
    "antigravity": {
        "name": "Google Antigravity / Gemini CLI",
        "source": os.path.join(SKILLS_SOURCE_DIR, "antigravity", "SKILL.md"),
        "target_rel": os.path.join(".gemini", "skills", "shokitora", "SKILL.md"),
        "aliases": ["agy", "gemini", "antigravity"]
    },
    "claude": {
        "name": "Anthropic Claude Code",
        "source": os.path.join(SKILLS_SOURCE_DIR, "claude_code", "CLAUDE.md"),
        "target_rel": "CLAUDE.md",
        "aliases": ["claude", "claude_code", "anthropic"]
    },
    "cursor": {
        "name": "Cursor AI IDE",
        "source": os.path.join(SKILLS_SOURCE_DIR, "cursor", ".cursorrules"),
        "target_rel": ".cursorrules",
        "aliases": ["cursor"]
    },
    "windsurf": {
        "name": "Windsurf Cascade",
        "source": os.path.join(SKILLS_SOURCE_DIR, "windsurf", ".windsurfrules"),
        "target_rel": ".windsurfrules",
        "aliases": ["windsurf", "cascade"]
    }
}


def resolve_agent_key(agent_str):
    if not agent_str:
        return "all"
    s = agent_str.strip().lower()
    if s == "all":
        return "all"
    for k, v in AGENTS.items():
        if s == k or s in v["aliases"]:
            return k
    return None


def install_agent_skill(key, target_dir=".", force=False):
    agent_info = AGENTS[key]
    source_file = agent_info["source"]
    target_file = os.path.join(target_dir, agent_info["target_rel"])

    if not os.path.exists(source_file):
        print(f"Error: Source skill template not found at {source_file}", file=sys.stderr)
        return False

    if os.path.exists(target_file) and not force:
        print(f"  • {agent_info['name']:<32} : Already installed ({agent_info['target_rel']})")
        return True

    os.makedirs(os.path.dirname(os.path.abspath(target_file)), exist_ok=True)
    shutil.copyfile(source_file, target_file)
    print(f"  ✓ {agent_info['name']:<32} -> {agent_info['target_rel']}")
    return True


def install_skills(agent="all", target_dir=".", force=False):
    resolved = resolve_agent_key(agent)
    if not resolved:
        print(f"Error: Unknown agent '{agent}'. Choose from: antigravity, claude, cursor, windsurf, all.", file=sys.stderr)
        sys.exit(1)

    print(f"\n🐯 Installing Shokitora Universal Agent Skills (Target: {os.path.abspath(target_dir)})")
    print("=" * 70)

    if resolved == "all":
        for k in AGENTS.keys():
            install_agent_skill(k, target_dir=target_dir, force=force)
    else:
        install_agent_skill(resolved, target_dir=target_dir, force=force)

    print("\n✓ Universal Agent Skills configured successfully!")
    print("  AI coding agents in this workspace are now grounded by Shokitora's technical ledger.")


def status_skills(target_dir="."):
    print(f"\n🐯 Shokitora Agent Skills Status (Directory: {os.path.abspath(target_dir)})")
    print("=" * 70)
    for k, v in AGENTS.items():
        target_path = os.path.join(target_dir, v["target_rel"])
        if os.path.exists(target_path):
            size = os.path.getsize(target_path)
            print(f"  ✓ {v['name']:<32} : ACTIVE ({v['target_rel']} - {size} bytes)")
        else:
            print(f"  ✗ {v['name']:<32} : NOT INSTALLED (Run: shoki skill install {k})")
    print("")


def list_skills():
    print("\n🐯 Shokitora Supported Universal Agent Skills")
    print("=" * 70)
    for k, v in AGENTS.items():
        aliases_str = ", ".join(v["aliases"])
        print(f"  • {k:<12} : {v['name']} (Aliases: {aliases_str})")
        print(f"    Target File: {v['target_rel']}\n")


def main():
    parser = argparse.ArgumentParser(
        prog="shoki skill",
        description="Shokitora Universal Agent Skill Installer (Antigravity, Claude Code, Cursor, Windsurf)"
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # install
    p_inst = subparsers.add_parser("install", help="Install universal agent skill or dotfiles")
    p_inst.add_argument("agent", nargs="?", default="all", help="Target agent: antigravity, claude, cursor, windsurf, or all (default: all)")
    p_inst.add_argument("--force", action="store_true", help="Overwrite existing configuration files")
    p_inst.add_argument("--dir", default=".", help="Target project root directory (default: current directory)")

    # status
    p_stat = subparsers.add_parser("status", help="Check status of agent skill files in workspace")
    p_stat.add_argument("--dir", default=".", help="Target directory (default: current directory)")

    # list
    subparsers.add_parser("list", help="List all supported agent platforms")

    args = parser.parse_args()

    if args.subcommand == "install":
        install_skills(agent=args.agent, target_dir=args.dir, force=args.force)
    elif args.subcommand == "status":
        status_skills(target_dir=args.dir)
    elif args.subcommand == "list":
        list_skills()


if __name__ == "__main__":
    main()
