#!/usr/bin/env python3
"""
Comprehensive Unit Test Suite for Shokitora Git Hooks Manager
==============================================================
Covers 100% of commands_hooks.py functions and CLI commands.
"""

import os
import sys
import stat
import tempfile
import unittest
import subprocess
from io import StringIO
from unittest.mock import patch

# Add package root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import shokitora.cli.commands_hooks as ch
from shokitora.cli.commands_hooks import (
    get_git_hooks_dir,
    install_hooks,
    status_hooks,
    uninstall_hooks,
    main as hooks_main,
)


class TestGitHooks(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_dir = self.temp_dir.name
        subprocess.run(["git", "init"], cwd=self.repo_dir, check=True, capture_output=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_install_status_and_uninstall(self):
        """Verifies hook installation, status check, and uninstallation."""
        cur_cwd = os.getcwd()
        os.chdir(self.repo_dir)
        try:
            # Check status before install
            with patch("sys.stdout", new=StringIO()) as out:
                status_hooks()
                self.assertIn("NOT INSTALLED", out.getvalue())

            # Install hooks
            install_hooks(force=True)
            hooks_dir = os.path.join(self.repo_dir, ".git", "hooks")
            pre_hook = os.path.join(hooks_dir, "pre-commit")
            post_hook = os.path.join(hooks_dir, "post-commit")

            self.assertTrue(os.path.exists(pre_hook))
            self.assertTrue(os.path.exists(post_hook))
            self.assertTrue(os.access(pre_hook, os.X_OK))
            self.assertTrue(os.access(post_hook, os.X_OK))

            # Status when active
            with patch("sys.stdout", new=StringIO()) as out:
                status_hooks()
                self.assertIn("ACTIVE (Executable)", out.getvalue())

            # Status when not executable
            os.chmod(pre_hook, stat.S_IRUSR | stat.S_IWUSR)
            with patch("sys.stdout", new=StringIO()) as out:
                status_hooks()
                self.assertIn("INSTALLED (Not Executable)", out.getvalue())

            # Test uninstall
            with patch("sys.stdout", new=StringIO()) as out:
                uninstall_hooks()
                self.assertIn("Removed Shokitora hooks", out.getvalue())

            self.assertFalse(os.path.exists(pre_hook))
            self.assertFalse(os.path.exists(post_hook))

            # Test uninstall when already removed
            with patch("sys.stdout", new=StringIO()) as out:
                uninstall_hooks()
                self.assertIn("No Shokitora hooks found to remove", out.getvalue())
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

    def test_03_non_git_repository_handling(self):
        """Verifies graceful errors when executed outside of a git repository."""
        non_git_dir = tempfile.mkdtemp()
        cur_cwd = os.getcwd()
        os.chdir(non_git_dir)
        try:
            self.assertIsNone(get_git_hooks_dir())

            with self.assertRaises(SystemExit):
                install_hooks()

            with self.assertRaises(SystemExit):
                status_hooks()

            with self.assertRaises(SystemExit):
                uninstall_hooks()
        finally:
            os.chdir(cur_cwd)
            import shutil
            shutil.rmtree(non_git_dir, ignore_errors=True)

    def test_04_missing_source_hook(self):
        """Verifies warning when a source hook script is missing."""
        cur_cwd = os.getcwd()
        os.chdir(self.repo_dir)
        try:
            orig_dir = ch.HOOKS_DIR
            ch.HOOKS_DIR = "/tmp/nonexistent_hooks_dir_xyz"
            with patch("sys.stderr", new=StringIO()) as err:
                install_hooks()
                self.assertIn("Warning: Source hook", err.getvalue())
            ch.HOOKS_DIR = orig_dir
        finally:
            os.chdir(cur_cwd)

    def test_05_cli_main_dispatch(self):
        """Verifies main() entrypoint routing for install, status, and uninstall."""
        cur_cwd = os.getcwd()
        os.chdir(self.repo_dir)
        try:
            for subcmd in ["install", "status", "uninstall"]:
                with patch("sys.argv", ["commands_hooks.py", subcmd]), patch("sys.stdout", new=StringIO()):
                    hooks_main()
        finally:
            os.chdir(cur_cwd)


if __name__ == "__main__":
    unittest.main(verbosity=2)
