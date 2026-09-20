#!/usr/bin/env python3
"""
Comprehensive Unit Test Suite for Shokitora Universal Agent Skills Installer
==============================================================================
Covers 100% of commands_skill.py functions and CLI commands.
"""

import os
import sys
import tempfile
import unittest
from io import StringIO
from unittest.mock import patch

# Add package root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import shokitora.cli.commands_skill as cs
from shokitora.cli.commands_skill import (
    install_skills,
    install_agent_skill,
    status_skills,
    list_skills,
    resolve_agent_key,
    AGENTS,
    main as skill_main,
)


class TestAgentSkills(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.target_dir = self.temp_dir.name

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_agent_key_resolution(self):
        """Verifies resolution of agent names and aliases."""
        self.assertEqual(resolve_agent_key("antigravity"), "antigravity")
        self.assertEqual(resolve_agent_key("agy"), "antigravity")
        self.assertEqual(resolve_agent_key("gemini"), "antigravity")
        self.assertEqual(resolve_agent_key("claude"), "claude")
        self.assertEqual(resolve_agent_key("claude_code"), "claude")
        self.assertEqual(resolve_agent_key("cursor"), "cursor")
        self.assertEqual(resolve_agent_key("windsurf"), "windsurf")
        self.assertEqual(resolve_agent_key("all"), "all")
        self.assertEqual(resolve_agent_key(None), "all")
        self.assertIsNone(resolve_agent_key("unknown_agent"))

    def test_02_install_individual_agent(self):
        """Verifies installing a single agent skill."""
        install_skills(agent="antigravity", target_dir=self.target_dir)
        skill_path = os.path.join(self.target_dir, ".gemini", "skills", "shokitora", "SKILL.md")
        self.assertTrue(os.path.exists(skill_path))
        with open(skill_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("name: shokitora", content)
        self.assertIn("shoki task:list", content)

    def test_03_install_all_agents(self):
        """Verifies installing all universal agent skill files."""
        install_skills(agent="all", target_dir=self.target_dir)
        for k, v in AGENTS.items():
            installed_path = os.path.join(self.target_dir, v["target_rel"])
            self.assertTrue(os.path.exists(installed_path), f"Missing {v['target_rel']}")
            self.assertGreater(os.path.getsize(installed_path), 50)

    def test_04_already_installed_and_force(self):
        """Verifies warning when already installed, and overwrite when force=True."""
        install_skills(agent="cursor", target_dir=self.target_dir)

        # Re-install without force should print 'Already installed'
        with patch("sys.stdout", new=StringIO()) as out:
            install_skills(agent="cursor", target_dir=self.target_dir, force=False)
            self.assertIn("Already installed", out.getvalue())

        # Re-install with force should overwrite
        with patch("sys.stdout", new=StringIO()) as out:
            install_skills(agent="cursor", target_dir=self.target_dir, force=True)
            self.assertIn("-> .cursorrules", out.getvalue())

    def test_05_unknown_agent_error(self):
        """Verifies error and SystemExit when an unknown agent name is supplied."""
        with self.assertRaises(SystemExit):
            install_skills(agent="invalid_bot", target_dir=self.target_dir)

    def test_06_missing_source_template(self):
        """Verifies error handling when a source template does not exist."""
        orig_source = AGENTS["antigravity"]["source"]
        AGENTS["antigravity"]["source"] = "/tmp/nonexistent_template_xyz"
        try:
            with patch("sys.stderr", new=StringIO()) as err:
                ok = install_agent_skill("antigravity", target_dir=self.target_dir)
                self.assertFalse(ok)
                self.assertIn("Error: Source skill template not found", err.getvalue())
        finally:
            AGENTS["antigravity"]["source"] = orig_source

    def test_07_status_and_list_skills(self):
        """Verifies status_skills and list_skills output formatting."""
        # Status before installation
        with patch("sys.stdout", new=StringIO()) as out:
            status_skills(target_dir=self.target_dir)
            self.assertIn("NOT INSTALLED", out.getvalue())

        # Install and check status
        install_skills(agent="all", target_dir=self.target_dir)
        with patch("sys.stdout", new=StringIO()) as out:
            status_skills(target_dir=self.target_dir)
            self.assertIn("ACTIVE", out.getvalue())

        # List skills
        with patch("sys.stdout", new=StringIO()) as out:
            list_skills()
            out_str = out.getvalue()
            self.assertIn("antigravity", out_str)
            self.assertIn("claude", out_str)
            self.assertIn("cursor", out_str)
            self.assertIn("windsurf", out_str)

    def test_08_cli_main_dispatch(self):
        """Verifies main() entrypoint routing for install, status, and list."""
        commands = [
            ["commands_skill.py", "install", "antigravity", "--dir", self.target_dir],
            ["commands_skill.py", "status", "--dir", self.target_dir],
            ["commands_skill.py", "list"],
        ]
        for cmd_args in commands:
            with patch("sys.argv", cmd_args), patch("sys.stdout", new=StringIO()):
                skill_main()


if __name__ == "__main__":
    unittest.main(verbosity=2)
