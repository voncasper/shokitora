#!/usr/bin/env python3
"""
Comprehensive Unit Test Suite for Shokitora Master CLI Router
=============================================================
Covers 100% of main.py and commands_vault.py functions and dispatching.
"""

import os
import sys
import unittest
from io import StringIO
from unittest.mock import patch, MagicMock

# Add package root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shokitora.cli.main import print_help, main as cli_main
from shokitora.cli.commands_vault import main as vault_wrapper_main


class TestCLIRouter(unittest.TestCase):

    def test_01_help_and_version(self):
        """Verifies help output and version flag handling."""
        with patch("sys.stdout", new=StringIO()) as out:
            print_help()
            self.assertIn("The Sovereign Tiger Scribe", out.getvalue())

        # Test help flag exiting 0
        for flag in ["-h", "--help", "help"]:
            with patch("sys.argv", ["shoki", flag]), self.assertRaises(SystemExit) as cm:
                cli_main()
            self.assertEqual(cm.exception.code, 0)

        # Test empty arguments exiting 0
        with patch("sys.argv", ["shoki"]), self.assertRaises(SystemExit) as cm:
            cli_main()
        self.assertEqual(cm.exception.code, 0)

        # Test version flag exiting 0
        for flag in ["-v", "--version", "version"]:
            with patch("sys.argv", ["shoki", flag]), patch("sys.stdout", new=StringIO()) as out, \
                 self.assertRaises(SystemExit) as cm:
                cli_main()
            self.assertEqual(cm.exception.code, 0)
            self.assertIn("Shokitora (書記虎)", out.getvalue())

    def test_02_route_skill_commands(self):
        """Verifies routing for skill aliases."""
        skill_routes = ["skill", "skill:install", "skill:status", "skill:list", "skills"]
        for cmd in skill_routes:
            with patch("sys.argv", ["shoki", cmd]), \
                 patch("shokitora.cli.commands_skill.main") as mock_skill_main:
                cli_main()
                mock_skill_main.assert_called_once()

    def test_03_route_hooks_commands(self):
        """Verifies routing for hooks aliases."""
        hooks_routes = ["hooks", "hooks:install", "hooks:status"]
        for cmd in hooks_routes:
            with patch("sys.argv", ["shoki", cmd]), \
                 patch("shokitora.cli.commands_hooks.main") as mock_hooks_main:
                cli_main()
                mock_hooks_main.assert_called_once()

    def test_04_route_vault_and_ctp(self):
        """Verifies routing for vault and ctp subcommands."""
        with patch("sys.argv", ["shoki", "vault", "status"]), \
             patch("shokitora.core.vault.main") as mock_vault_main:
            cli_main()
            mock_vault_main.assert_called_once()

        with patch("sys.argv", ["shoki", "ctp", "feat: test"]), \
             patch("shokitora.cli.commands_ctp.main") as mock_ctp_main:
            cli_main()
            mock_ctp_main.assert_called_once()

    def test_05_route_journal_commands(self):
        """Verifies routing journal commands to journal_db.py."""
        with patch("sys.argv", ["shoki", "task:list"]), \
             patch("shokitora.core.journal_db.main") as mock_journal_main:
            cli_main()
            mock_journal_main.assert_called_once()

    def test_06_commands_vault_wrapper(self):
        """Verifies commands_vault.py CLI wrapper."""
        with patch("shokitora.cli.commands_vault.vault_main") as mock_vault_main:
            vault_wrapper_main()
            mock_vault_main.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
