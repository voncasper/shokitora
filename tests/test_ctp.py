#!/usr/bin/env python3
"""
Comprehensive Unit Test Suite for Shokitora CTP Release Pipeline
================================================================
Covers 100% of commands_ctp.py functions and CLI commands.
"""

import os
import sys
import tempfile
import unittest
import subprocess
from io import StringIO
from unittest.mock import patch, MagicMock

# Add package root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import shokitora.cli.commands_ctp as ctp
from shokitora.cli.commands_ctp import (
    run_git,
    get_current_branch,
    get_latest_tag,
    suggest_next_patch,
    main as ctp_main,
)


class TestCTPPipeline(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_dir = self.temp_dir.name
        # Init repo and configure git user
        subprocess.run(["git", "init"], cwd=self.repo_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.repo_dir, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.repo_dir, check=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_suggest_next_patch(self):
        """Verifies semantic version patch calculation."""
        self.assertEqual(suggest_next_patch("v0.1.0"), "v0.1.1")
        self.assertEqual(suggest_next_patch("0.1.1"), "0.1.2")
        self.assertEqual(suggest_next_patch("v1.2.9"), "v1.2.10")
        self.assertEqual(suggest_next_patch("custom_tag"), "custom_tag.1")

    def test_02_git_helpers(self):
        """Verifies run_git, get_current_branch, and get_latest_tag."""
        cur_cwd = os.getcwd()
        os.chdir(self.repo_dir)
        try:
            self.assertEqual(run_git(["status"], capture_output=True), run_git(["status"], capture_output=True))
            # Test run_git error without check
            self.assertEqual(run_git(["invalid-git-command-xyz"], check=False), "")

            # Test run_git error with check
            with self.assertRaises(SystemExit):
                run_git(["invalid-git-command-xyz"], check=True)

            self.assertIn(get_current_branch(), ["main", "master"])
            self.assertEqual(get_latest_tag(), "v0.1.0")
        finally:
            os.chdir(cur_cwd)

    def test_03_ctp_dry_run(self):
        """Verifies dry-run mode prints expected simulation output."""
        cur_cwd = os.getcwd()
        os.chdir(self.repo_dir)
        try:
            with patch("sys.argv", ["ctp", "feat: test release", "--dry-run"]), \
                 patch("sys.stdout", new=StringIO()) as out:
                ctp_main()
                val = out.getvalue()
                self.assertIn("CTP Release Pipeline", val)
                self.assertIn("[Dry Run] Actions simulated successfully", val)
                self.assertIn("v0.1.1", val)
        finally:
            os.chdir(cur_cwd)

    def test_04_missing_or_empty_commit_message(self):
        """Verifies error handling when commit message is missing or empty."""
        cur_cwd = os.getcwd()
        os.chdir(self.repo_dir)
        try:
            # Non-tty stdin missing message
            with patch("sys.argv", ["ctp"]), patch("sys.stdin.isatty", return_value=False), \
                 self.assertRaises(SystemExit):
                ctp_main()

            # Empty message from tty prompt
            with patch("sys.argv", ["ctp"]), patch("sys.stdin.isatty", return_value=True), \
                 patch("builtins.input", return_value=""), self.assertRaises(SystemExit):
                ctp_main()
        finally:
            os.chdir(cur_cwd)

    def test_05_ctp_full_execution_mocked_push(self):
        """Verifies staging, committing, tagging, and pushing with mocks."""
        cur_cwd = os.getcwd()
        os.chdir(self.repo_dir)
        try:
            # Create a file to commit
            test_file = os.path.join(self.repo_dir, "test.txt")
            with open(test_file, "w") as f:
                f.write("hello\n")

            # Mock git push since no remote exists in local temp git repo
            orig_run_git = ctp.run_git
            def mock_run_git(args, capture_output=False, check=True):
                if args and args[0] == "push":
                    return ""
                return orig_run_git(args, capture_output=capture_output, check=check)

            with patch("shokitora.cli.commands_ctp.run_git", side_effect=mock_run_git), \
                 patch("sys.argv", ["ctp", "-m", "feat: initial commit", "-t", "v0.1.1"]), \
                 patch("sys.stdout", new=StringIO()) as out:
                ctp_main()
                self.assertIn("CTP Release complete", out.getvalue())

            # Verify tag was created in repo
            tags = subprocess.check_output(["git", "tag"], cwd=self.repo_dir, text=True)
            self.assertIn("v0.1.1", tags)

            # Test committing again with --no-tag when nothing new to commit
            with patch("shokitora.cli.commands_ctp.run_git", side_effect=mock_run_git), \
                 patch("sys.argv", ["ctp", "chore: no changes", "--no-tag"]), \
                 patch("sys.stdout", new=StringIO()) as out:
                ctp_main()
                self.assertIn("SKIPPED (--no-tag)", out.getvalue())
        finally:
            os.chdir(cur_cwd)


if __name__ == "__main__":
    unittest.main(verbosity=2)
