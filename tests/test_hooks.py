#!/usr/bin/env python3
"""
Unit Test Suite for Shokitora Git Hooks Manager
===============================================
"""

import os
import sys
import stat
import tempfile
import unittest
import subprocess

# Add package root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shokitora.cli.commands_hooks import install_hooks, status_hooks, uninstall_hooks


class TestGitHooks(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_dir = self.temp_dir.name
        subprocess.run(["git", "init"], cwd=self.repo_dir, check=True, capture_output=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_install_and_status(self):
        """Verifies hooks install into .git/hooks/ and are marked executable."""
        cur_cwd = os.getcwd()
        os.chdir(self.repo_dir)
        try:
            install_hooks(force=True)
            hooks_dir = os.path.join(self.repo_dir, ".git", "hooks")
            pre_hook = os.path.join(hooks_dir, "pre-commit")
            post_hook = os.path.join(hooks_dir, "post-commit")

            self.assertTrue(os.path.exists(pre_hook))
            self.assertTrue(os.path.exists(post_hook))

            self.assertTrue(os.access(pre_hook, os.X_OK))
            self.assertTrue(os.access(post_hook, os.X_OK))

            # Test uninstall
            uninstall_hooks()
            self.assertFalse(os.path.exists(pre_hook))
            self.assertFalse(os.path.exists(post_hook))
        finally:
            os.chdir(cur_cwd)

    def test_02_pre_commit_blocks_env_file(self):
        """Verifies pre-commit hook aborts when a plaintext .env file is staged."""
        cur_cwd = os.getcwd()
        os.chdir(self.repo_dir)
        try:
            install_hooks(force=True)

            # Create and stage .env
            with open(os.path.join(self.repo_dir, ".env"), "w") as f:
                f.write("SECRET_KEY=12345\n")
            subprocess.run(["git", "add", ".env"], cwd=self.repo_dir, check=True)

            # Execute pre-commit hook
            hook_path = os.path.join(self.repo_dir, ".git", "hooks", "pre-commit")
            res = subprocess.run([hook_path], cwd=self.repo_dir, capture_output=True, text=True)
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("Plaintext .env file staged", res.stdout)
        finally:
            os.chdir(cur_cwd)


if __name__ == "__main__":
    unittest.main(verbosity=2)
