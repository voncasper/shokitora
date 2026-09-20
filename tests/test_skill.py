#!/usr/bin/env python3
"""
Unit Test Suite for Shokitora Universal Agent Skills Installer
==============================================================
"""

import os
import sys
import tempfile
import unittest

# Add package root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shokitora.cli.commands_skill import install_skills, resolve_agent_key, AGENTS


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
