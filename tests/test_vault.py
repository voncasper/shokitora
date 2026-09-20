#!/usr/bin/env python3
"""
Unit Test Suite for Shokitora CPU-Bound Sovereign Vault
======================================================
"""

import os
import sys
import json
import tempfile
import unittest
import subprocess
from pathlib import Path

# Add package root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shokitora.core.vault import (
    ScribeVault,
    get_host_hardware_fingerprint,
    derive_key_from_seed,
    derive_key_from_passphrase,
    parse_expiry,
    compute_expiry_metadata,
    get_secret,
    set_secret,
    delete_secret,
    list_secrets,
    audit_secrets,
    triage_secrets,
    load_secrets_into_environ
)


class TestShokitoraVault(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault_file = os.path.join(self.temp_dir.name, "test_vault.enc")
        self.vault = ScribeVault(vault_path=self.vault_file)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_hardware_fingerprint_detection(self):
        """Verifies host hardware fingerprint fields and SHA256 integrity."""
        hw = get_host_hardware_fingerprint()
        self.assertIn("os", hw)
        self.assertIn("arch", hw)
        self.assertIn("system_uuid_masked", hw)
        self.assertIn("cpu_detail", hw)
        self.assertIn("fingerprint_sha256", hw)
        self.assertIn("seed", hw)
        self.assertEqual(len(hw["fingerprint_sha256"]), 64)
        self.assertTrue(hw["seed"].startswith("SCRIBE_HOST:"))

    def test_02_key_derivation_deterministic(self):
        """Verifies HKDF-SHA256 key derivation is deterministic and unique."""
        seed_a = "SCRIBE_HOST:Linux:x86_64:UUID-1234:Intel Xeon"
        seed_b = "SCRIBE_HOST:Linux:x86_64:UUID-5678:Intel Xeon"
        key_a1 = derive_key_from_seed(seed_a)
        key_a2 = derive_key_from_seed(seed_a)
        key_b = derive_key_from_seed(seed_b)

        self.assertEqual(len(key_a1), 32)
        self.assertEqual(key_a1, key_a2)
        self.assertNotEqual(key_a1, key_b)

    def test_03_crud_operations(self):
        """Verifies set, get, list, and delete operations."""
        self.assertIsNone(self.vault.get("NON_EXISTENT"))

        self.vault.set("GEMINI_API_KEY", "AIzaSyTestKey123456789", description="Test Gemini Key")
        self.assertEqual(self.vault.get("GEMINI_API_KEY"), "AIzaSyTestKey123456789")

        self.vault.set("GEMINI_API_KEY", "AIzaSyUpdatedKey987654321")
        self.assertEqual(self.vault.get("GEMINI_API_KEY"), "AIzaSyUpdatedKey987654321")

        secrets = self.vault.list()
        self.assertEqual(len(secrets), 1)
        self.assertEqual(secrets[0]["key"], "GEMINI_API_KEY")
        self.assertTrue(secrets[0]["masked_preview"].startswith("****"))
        self.assertTrue(secrets[0]["masked_preview"].endswith("4321"))

        self.assertTrue(self.vault.delete("GEMINI_API_KEY"))
        self.assertIsNone(self.vault.get("GEMINI_API_KEY"))

    def test_04_tamper_detection(self):
        """Verifies AES-256-GCM authentication detects file tampering."""
        self.vault.set("SUPER_SECRET", "ConfidentialValue")
        self.assertTrue(os.path.exists(self.vault_file))

        with open(self.vault_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        raw_ct = list(data["ciphertext"])
        raw_ct[0] = "f" if raw_ct[0] != "f" else "0"
        data["ciphertext"] = "".join(raw_ct)

        with open(self.vault_file, "w", encoding="utf-8") as f:
            json.dump(data, f)

        tampered_vault = ScribeVault(vault_path=self.vault_file)
        with self.assertRaises(PermissionError):
            tampered_vault.get("SUPER_SECRET")

    def test_05_import_env_and_shred(self):
        """Verifies importing .env files and securely shredding the plaintext source."""
        env_content = (
            "# Developer Configuration\n"
            "TELEGRAM_BOT_TOKEN=\"987654321:AAF-FakeToken_XYZ\"\n"
            "DATABASE_URL='sqlite:///journal.db'\n"
            "DEBUG=True\n"
        )
        test_env_path = os.path.join(self.temp_dir.name, ".env.test")
        with open(test_env_path, "w", encoding="utf-8") as f:
            f.write(env_content)

        count = self.vault.import_env(test_env_path, delete_source=True)
        self.assertEqual(count, 3)
        self.assertFalse(os.path.exists(test_env_path))
        self.assertEqual(self.vault.get("TELEGRAM_BOT_TOKEN"), "987654321:AAF-FakeToken_XYZ")

    def test_06_run_command_environment_injection(self):
        """Verifies 'run_command' injects secrets into child process in-memory."""
        self.vault.set("INJECTED_TEST_VAR", "HardwareBoundSecret42")

        cmd = [
            sys.executable,
            "-c",
            "import os, sys; val = os.environ.get('INJECTED_TEST_VAR'); sys.exit(0 if val == 'HardwareBoundSecret42' else 1)"
        ]
        exit_code = self.vault.run_command(cmd)
        self.assertEqual(exit_code, 0)

    def test_07_migration_bundle_export_and_import(self):
        """Verifies password-encrypted migration bundle across machines."""
        self.vault.set("GITHUB_TOKEN", "ghp_MockSecretToken777")

        bundle_path = os.path.join(self.temp_dir.name, "migration.bundle.json")
        passphrase = "MasterDeveloperPassphrase2026!"

        self.vault.export_migratable_bundle(bundle_path, passphrase)
        self.assertTrue(os.path.exists(bundle_path))

        target_vault_file = os.path.join(self.temp_dir.name, "target_vault.enc")
        target_vault = ScribeVault(vault_path=target_vault_file)
        target_vault.import_migratable_bundle(bundle_path, passphrase)

        self.assertEqual(target_vault.get("GITHUB_TOKEN"), "ghp_MockSecretToken777")

    def test_08_expiration_relative_and_absolute(self):
        """Verifies parsing relative durations, absolute dates, and metadata computation."""
        # 90-day relative expiry
        self.vault.set("GITHUB_TOKEN", "ghp_MockPAT12345", description="GitHub PAT", expires_at=parse_expiry(expires_in="90d"))
        meta = compute_expiry_metadata(self.vault.list()[0]["expires_at"])
        self.assertEqual(meta["status"], "ACTIVE")
        self.assertGreaterEqual(meta["days_remaining"], 88)
        self.assertFalse(meta["is_expired"])
        self.assertFalse(meta["is_expiring_soon"])

        # Expiring soon (5 days)
        self.vault.set("EXPIRING_TOKEN", "ExpiringValue", expires_at=parse_expiry(expires_in="5d"))
        exp_item = [x for x in self.vault.list() if x["key"] == "EXPIRING_TOKEN"][0]
        self.assertEqual(exp_item["status"], "EXPIRING_SOON")
        self.assertTrue(exp_item["is_expiring_soon"])

        # Expired (2 days in past)
        from datetime import datetime, timezone, timedelta
        past_iso = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        self.vault.set("STALE_TOKEN", "ExpiredValue", expires_at=past_iso)
        stale_item = [x for x in self.vault.list() if x["key"] == "STALE_TOKEN"][0]
        self.assertEqual(stale_item["status"], "EXPIRED")
        self.assertTrue(stale_item["is_expired"])

        # Clear expiration policy
        self.vault.set("GITHUB_TOKEN", expires_at="CLEAR")
        cleared_item = [x for x in self.vault.list() if x["key"] == "GITHUB_TOKEN"][0]
        self.assertEqual(cleared_item["status"], "PERPETUAL")
        self.assertIsNone(cleared_item["expires_at"])

    def test_09_audit_posture_and_expiry(self):
        """Verifies audit categorization and health status."""
        self.vault.set("ACTIVE_KEY", "KeyVal1", expires_at=parse_expiry(expires_in="60d"))
        self.vault.set("WARN_KEY", "KeyVal2", expires_at=parse_expiry(expires_in="7d"))
        self.vault.set("PERPETUAL_KEY", "KeyVal3")

        rep = self.vault.audit(warn_days=14)
        self.assertEqual(rep["health"], "WARNING")
        self.assertEqual(rep["counts"]["total"], 3)
        self.assertEqual(rep["counts"]["active"], 1)
        self.assertEqual(rep["counts"]["expiring_soon"], 1)
        self.assertEqual(rep["counts"]["perpetual"], 1)
        self.assertEqual(rep["counts"]["expired"], 0)

    def test_10_triage_diagnostic_assistant(self):
        """Verifies triage diagnosis and remediation instructions."""
        self.vault.set("github/token", "ghp_DummyToken", expires_at=parse_expiry(expires_in="30d"))
        triage_res = self.vault.triage("github")
        self.assertEqual(len(triage_res), 1)
        self.assertEqual(triage_res[0]["service"], "GitHub")
        self.assertIn("github.com/settings/tokens", triage_res[0]["remediation_url"])
        self.assertIn("OK: Secret is active", triage_res[0]["diagnosis"])

    def test_11_metadata_only_update(self):
        """Verifies that updating expires_at or description preserves existing secret value."""
        self.vault.set("PRESERVED_KEY", "OriginalSecretValue42", description="Original Desc")
        self.assertEqual(self.vault.get("PRESERVED_KEY"), "OriginalSecretValue42")

        # Update expires_at without providing value
        self.vault.set("PRESERVED_KEY", expires_at=parse_expiry(expires_in="90d"))
        self.assertEqual(self.vault.get("PRESERVED_KEY"), "OriginalSecretValue42")
        self.assertIsNotNone(self.vault.list()[0]["expires_at"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
