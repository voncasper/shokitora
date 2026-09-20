#!/usr/bin/env python3
"""
Comprehensive Unit Test Suite for Shokitora CPU-Bound Sovereign Vault
======================================================================
Covers 100% of vault.py cryptographic functions, key derivation,
multi-OS hardware probes, migration bundles, expiration, and CLI.
"""

import os
import sys
import json
import tempfile
import unittest
import subprocess
from io import StringIO
from unittest.mock import patch, mock_open, MagicMock

# Add package root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import shokitora.core.vault as sv
from shokitora.core.vault import (
    ScribeVault,
    get_default_vault_path,
    get_host_hardware_fingerprint,
    derive_key_from_seed,
    derive_key_from_passphrase,
    parse_expiry,
    compute_expiry_metadata,
    get_remediation_info,
    get_remediation_url,
    get_secret,
    set_secret,
    delete_secret,
    list_secrets,
    audit_secrets,
    triage_secrets,
    load_secrets_into_environ,
    main as vault_main,
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
        """Verifies set, get, list, delete operations, and short values."""
        self.assertIsNone(self.vault.get("NON_EXISTENT"))
        self.assertFalse(self.vault.delete("NON_EXISTENT"))

        # Test creating secret without value raises ValueError
        with self.assertRaises(ValueError):
            self.vault.set("UNSET_KEY", value=None)

        # Value with <= 4 characters (preview is '****')
        self.vault.set("PIN", "1234")
        self.assertEqual(self.vault.get("PIN"), "1234")
        secrets = self.vault.list()
        self.assertEqual(secrets[0]["masked_preview"], "****")

        self.vault.set("GEMINI_API_KEY", "AIzaSyTestKey123456789", description="Test Gemini Key")
        self.assertEqual(self.vault.get("GEMINI_API_KEY"), "AIzaSyTestKey123456789")

        self.vault.set("GEMINI_API_KEY", "AIzaSyUpdatedKey987654321")
        self.assertEqual(self.vault.get("GEMINI_API_KEY"), "AIzaSyUpdatedKey987654321")

        secrets = self.vault.list()
        self.assertEqual(len(secrets), 2)
        gemini_entry = [s for s in secrets if s["key"] == "GEMINI_API_KEY"][0]
        self.assertTrue(gemini_entry["masked_preview"].startswith("****"))
        self.assertTrue(gemini_entry["masked_preview"].endswith("4321"))

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
        """Verifies importing .env files, quotes stripping, and shredding."""
        # Non-existent env file raises FileNotFoundError
        with self.assertRaises(FileNotFoundError):
            self.vault.import_env("/tmp/nonexistent_env_xyz.env")

        env_content = (
            "# Developer Configuration\n"
            "\n"
            "TELEGRAM_BOT_TOKEN=\"987654321:AAF-FakeToken_XYZ\"\n"
            "DATABASE_URL='sqlite:///journal.db'\n"
            "UNQUOTED=RawValue\n"
        )
        test_env_path = os.path.join(self.temp_dir.name, ".env.test")
        with open(test_env_path, "w", encoding="utf-8") as f:
            f.write(env_content)

        count = self.vault.import_env(test_env_path, delete_source=True)
        self.assertEqual(count, 3)
        self.assertFalse(os.path.exists(test_env_path))
        self.assertEqual(self.vault.get("TELEGRAM_BOT_TOKEN"), "987654321:AAF-FakeToken_XYZ")
        self.assertEqual(self.vault.get("DATABASE_URL"), "sqlite:///journal.db")
        self.assertEqual(self.vault.get("UNQUOTED"), "RawValue")

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

        # Non-existent command returns 1
        with patch("sys.stderr", new=StringIO()):
            err_code = self.vault.run_command(["nonexistent_binary_xyz_12345"])
            self.assertEqual(err_code, 1)

    def test_07_migration_bundle_export_and_import(self):
        """Verifies password-encrypted migration bundle across machines with merge and overwrite."""
        self.vault.set("GITHUB_TOKEN", "ghp_MockSecretToken777")

        bundle_path = os.path.join(self.temp_dir.name, "migration.bundle.json")
        passphrase = "MasterDeveloperPassphrase2026!"

        self.vault.export_migratable_bundle(bundle_path, passphrase)
        self.assertTrue(os.path.exists(bundle_path))

        target_vault_file = os.path.join(self.temp_dir.name, "target_vault.enc")
        target_vault = ScribeVault(vault_path=target_vault_file)
        target_vault.set("PRE_EXISTING", "KeepMe")

        # Import with overwrite=False (merges existing secrets)
        target_vault.import_migratable_bundle(bundle_path, passphrase, overwrite=False)
        self.assertEqual(target_vault.get("GITHUB_TOKEN"), "ghp_MockSecretToken777")
        self.assertEqual(target_vault.get("PRE_EXISTING"), "KeepMe")

        # Import with overwrite=True
        target_vault.import_migratable_bundle(bundle_path, passphrase, overwrite=True)
        self.assertEqual(target_vault.get("GITHUB_TOKEN"), "ghp_MockSecretToken777")

    def test_08_expiration_relative_and_absolute(self):
        """Verifies parsing relative durations (h, m, y, raw), absolute dates, and errors."""
        # Relative formats
        self.assertIsNotNone(parse_expiry(expires_in="48h"))
        self.assertIsNotNone(parse_expiry(expires_in="3m"))
        self.assertIsNotNone(parse_expiry(expires_in="2y"))
        self.assertIsNotNone(parse_expiry(expires_in="90"))
        with self.assertRaises(ValueError):
            parse_expiry(expires_in="invalid_duration")

        # Absolute formats
        self.assertEqual(parse_expiry(expires="NONE"), "CLEAR")
        self.assertEqual(parse_expiry(expires="CLEAR"), "CLEAR")
        self.assertIsNotNone(parse_expiry(expires="2026-12-31"))
        self.assertIsNotNone(parse_expiry(expires="2026-12-31T23:59:59Z"))
        with self.assertRaises(ValueError):
            parse_expiry(expires="not-a-date")

        # compute_expiry_metadata with unparseable string fallback
        meta_err = compute_expiry_metadata("unparseable-date")
        self.assertEqual(meta_err["status"], "UNKNOWN")

        # Timestamp without timezone offset
        meta_no_tz = compute_expiry_metadata("2026-12-31T23:59:59")
        self.assertEqual(meta_no_tz["status"], "ACTIVE")

        # 90-day relative expiry
        self.vault.set("GITHUB_TOKEN", "ghp_MockPAT12345", description="GitHub PAT", expires_at=parse_expiry(expires_in="90d"))
        meta = compute_expiry_metadata(self.vault.list()[0]["expires_at"])
        self.assertEqual(meta["status"], "ACTIVE")
        self.assertGreaterEqual(meta["days_remaining"], 88)

        # Expired (2 days in past)
        from datetime import datetime, timezone, timedelta
        past_iso = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        self.vault.set("STALE_TOKEN", "ExpiredValue", expires_at=past_iso)
        stale_item = [x for x in self.vault.list() if x["key"] == "STALE_TOKEN"][0]
        self.assertEqual(stale_item["status"], "EXPIRED")

        # Clear expiration
        self.vault.set("GITHUB_TOKEN", expires_at="CLEAR")
        cleared_item = [x for x in self.vault.list() if x["key"] == "GITHUB_TOKEN"][0]
        self.assertEqual(cleared_item["status"], "PERPETUAL")

    def test_09_audit_posture_critical_and_warning(self):
        """Verifies audit categorization with expired (CRITICAL) and expiring soon (WARNING)."""
        from datetime import datetime, timezone, timedelta
        past_iso = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

        self.vault.set("EXPIRED_KEY", "KeyVal1", expires_at=past_iso)
        self.vault.set("WARN_KEY", "KeyVal2", expires_at=parse_expiry(expires_in="7d"))
        self.vault.set("PERPETUAL_KEY", "KeyVal3")

        rep = self.vault.audit(warn_days=14)
        self.assertEqual(rep["health"], "CRITICAL")
        self.assertEqual(rep["counts"]["expired"], 1)
        self.assertEqual(rep["counts"]["expiring_soon"], 1)
        self.assertEqual(rep["counts"]["perpetual"], 1)

    def test_10_triage_diagnostic_assistant(self):
        """Verifies triage diagnosis for expired, expiring, and perpetual secrets."""
        from datetime import datetime, timezone, timedelta
        past_iso = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

        self.vault.set("github/token", "ghp_DummyToken", expires_at=past_iso)
        self.vault.set("gemini/api_key", "AIzaSyTest", expires_at=parse_expiry(expires_in="3d"))
        self.vault.set("custom/secret", "Val123")

        triage_all = self.vault.triage()
        self.assertEqual(len(triage_all), 3)

        # Query filter
        triage_gh = self.vault.triage("github")
        self.assertEqual(len(triage_gh), 1)
        self.assertEqual(triage_gh[0]["service"], "GitHub")
        self.assertIn("CRITICAL: Secret expired", triage_gh[0]["diagnosis"])

        self.assertEqual(get_remediation_url("github/token"), "https://github.com/settings/tokens")
        self.assertEqual(get_remediation_url("custom_unmatched"), "N/A")

    def test_11_status_and_export_env(self):
        """Verifies status dictionary and export_env string / file modes."""
        self.vault.set("PORT", "8080")
        self.vault.set("GREETING", "Hello World\nWith Newline")

        st = self.vault.status()
        self.assertTrue(st["exists"])
        self.assertEqual(st["secrets_count"], 2)

        # export_env to string
        env_str = self.vault.export_env()
        self.assertIn("PORT=8080", env_str)
        self.assertIn("GREETING=", env_str)

        # export_env to file
        env_out_path = os.path.join(self.temp_dir.name, "exported.env")
        self.vault.export_env(output_path=env_out_path)
        self.assertTrue(os.path.exists(env_out_path))

    def test_12_default_vault_path_resolution(self):
        """Verifies get_default_vault_path resolution hierarchy."""
        # 1. SCRIBE_VAULT_PATH env var
        with patch.dict(os.environ, {"SCRIBE_VAULT_PATH": "/custom/path/vault.enc"}):
            self.assertEqual(get_default_vault_path(), "/custom/path/vault.enc")

        # 2. Local cwd .scribe_vault.enc
        cur_cwd = os.getcwd()
        os.chdir(self.temp_dir.name)
        try:
            local_vault = os.path.abspath(".scribe_vault.enc")
            with open(local_vault, "w") as f:
                f.write("{}")
            self.assertEqual(get_default_vault_path(), local_vault)
            os.remove(local_vault)

            # Test git root
            with patch("subprocess.check_output", return_value=self.temp_dir.name + "\n"):
                git_v = os.path.join(self.temp_dir.name, ".scribe_vault.enc")
                with open(git_v, "w") as f:
                    f.write("{}")
                self.assertEqual(get_default_vault_path(), git_v)
                os.remove(git_v)
                self.assertEqual(get_default_vault_path(), git_v)

            # 3. Fallback to home dir
            home_path = os.path.expanduser("~/.scribe/vault.enc")
            self.assertEqual(get_default_vault_path(), home_path)
        finally:
            os.chdir(cur_cwd)


    def test_13_hardware_fingerprint_darwin_and_windows_mocked(self):
        """Verifies Darwin and Windows platform hardware detection routines."""
        # Test Darwin (macOS)
        with patch("platform.system", return_value="Darwin"), \
             patch("platform.machine", return_value="arm64"), \
             patch("subprocess.check_output", side_effect=[
                 '    "IOPlatformUUID" = "MOCK-DARWIN-UUID-1234"\n',
                 "Apple M3 Pro\n"
             ]):
            hw_mac = get_host_hardware_fingerprint()
            self.assertEqual(hw_mac["os"], "Darwin")
            self.assertEqual(hw_mac["system_uuid_masked"], "MOCK...1234")
            self.assertIn("Apple M3 Pro", hw_mac["cpu_detail"])

        # Test Windows
        with patch("platform.system", return_value="Windows"), \
             patch("platform.machine", return_value="AMD64"), \
             patch("subprocess.check_output", side_effect=[
                 "MOCK-WIN-UUID-5678\n",
                 "Intel Core i9-14900K\n"
             ]):
            hw_win = get_host_hardware_fingerprint()
            self.assertEqual(hw_win["os"], "Windows")
            self.assertEqual(hw_win["system_uuid_masked"], "MOCK...5678")
            self.assertIn("Intel Core i9-14900K", hw_win["cpu_detail"])

    def test_14_top_level_convenience_api(self):
        """Verifies get_secret, set_secret, delete_secret, list_secrets, audit_secrets, triage_secrets, load_secrets_into_environ."""
        vault_file = os.path.join(self.temp_dir.name, "conv_vault.enc")
        set_secret("API_KEY", "TestSecretKey", vault_path=vault_file)
        self.assertEqual(get_secret("API_KEY", vault_path=vault_file), "TestSecretKey")
        self.assertEqual(get_secret("MISSING", default="default_val", vault_path=vault_file), "default_val")

        self.assertEqual(len(list_secrets(vault_path=vault_file)), 1)
        self.assertEqual(audit_secrets(vault_path=vault_file)["health"], "HEALTHY")
        self.assertEqual(len(triage_secrets(vault_path=vault_file)), 1)

        load_secrets_into_environ(vault_path=vault_file, override=True)
        self.assertEqual(os.environ.get("API_KEY"), "TestSecretKey")

        self.assertTrue(delete_secret("API_KEY", vault_path=vault_file))

    def test_15_cli_main_dispatch(self):
        """Verifies vault main() CLI routing for all commands and options."""
        vf = os.path.join(self.temp_dir.name, "cli_vault.enc")
        bundle_file = os.path.join(self.temp_dir.name, "cli_bundle.json")
        env_file = os.path.join(self.temp_dir.name, "cli.env")
        with open(env_file, "w") as f:
            f.write("KEY_FROM_ENV=Val123\n")

        commands = [
            ["scribe", "--vault", vf, "status"],
            ["scribe", "--vault", vf, "set", "CLI_KEY", "CLI_VAL", "--desc", "Test Secret", "--expires-in", "60d"],
            ["scribe", "--vault", vf, "set", "PERPETUAL_KEY", "PerpVal"],
            ["scribe", "--vault", vf, "set", "STDIN_KEY", "-", "--expires", "CLEAR"],
            ["scribe", "--vault", vf, "get", "CLI_KEY"],
            ["scribe", "--vault", vf, "get", "CLI_KEY", "--raw"],
            ["scribe", "--vault", vf, "list"],
            ["scribe", "--vault", vf, "list", "--json"],
            ["scribe", "--vault", vf, "audit"],
            ["scribe", "--vault", vf, "audit", "--json"],
            ["scribe", "--vault", vf, "triage"],
            ["scribe", "--vault", vf, "triage", "CLI", "--json"],
            ["scribe", "--vault", vf, "export-env"],
            ["scribe", "--vault", vf, "export-bundle", bundle_file, "--passphrase", "SecurePass123!"],
            ["scribe", "--vault", vf, "import-bundle", bundle_file, "--passphrase", "SecurePass123!", "--overwrite"],
            ["scribe", "--vault", vf, "import-env", env_file],
            ["scribe", "--vault", vf, "delete", "STDIN_KEY"],
        ]

        for cmd_args in commands:
            with patch("sys.argv", cmd_args), patch("sys.stdin", StringIO("SecretFromStdin\n")), \
                 patch("sys.stdout", new=StringIO()):
                vault_main()

        # Test run command exiting 0
        with patch("sys.argv", ["scribe", "--vault", vf, "run", "--", sys.executable, "-c", "import sys; sys.exit(0)"]), \
             patch("sys.stdout", new=StringIO()), self.assertRaises(SystemExit) as cm:
            vault_main()
        self.assertEqual(cm.exception.code, 0)

        # Error cases in CLI
        with patch("sys.argv", ["scribe", "--vault", vf, "get", "NONEXISTENT_KEY"]), \
             patch("sys.stderr", new=StringIO()), self.assertRaises(SystemExit):
            vault_main()

        with patch("sys.argv", ["scribe", "--vault", vf, "delete", "NONEXISTENT_KEY"]), \
             patch("sys.stderr", new=StringIO()), self.assertRaises(SystemExit):
            vault_main()


        # Empty list test
        empty_vf = os.path.join(self.temp_dir.name, "empty_vault.enc")
        with patch("sys.argv", ["scribe", "--vault", empty_vf, "list"]), \
             patch("sys.stdout", new=StringIO()) as out:
            vault_main()
            self.assertIn("No secrets currently stored", out.getvalue())

        # Audit with expired and expiring soon
        from datetime import datetime, timezone, timedelta
        past_iso = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        sv.set_secret("EXPIRED_CLI", "Val", expires_at=past_iso, vault_path=vf)
        sv.set_secret("EXPIRING_CLI", "Val", expires_at=parse_expiry(expires_in="5d"), vault_path=vf)
        with patch("sys.argv", ["scribe", "--vault", vf, "audit"]), \
             patch("sys.stdout", new=StringIO()) as out:
            vault_main()
            self.assertIn("EXPIRED SECRETS", out.getvalue())
            self.assertIn("SECRETS EXPIRING WITHIN", out.getvalue())

        # Triage with filter and no matches
        with patch("sys.argv", ["scribe", "--vault", vf, "triage", "CLI_KEY"]), \
             patch("sys.stdout", new=StringIO()) as out:
            vault_main()
            self.assertIn("Filter: 'CLI_KEY'", out.getvalue())

        with patch("sys.argv", ["scribe", "--vault", vf, "triage", "NOMATCH_KEY"]), \
             patch("sys.stdout", new=StringIO()) as out:
            vault_main()
            self.assertIn("No secrets found matching query", out.getvalue())

        # Import-env with delete-source
        tmp_env2 = os.path.join(self.temp_dir.name, "delete_me.env")
        with open(tmp_env2, "w") as f:
            f.write("TMP_VAR=123\n")
        with patch("sys.argv", ["scribe", "--vault", vf, "import-env", tmp_env2, "--delete-source"]), \
             patch("sys.stdout", new=StringIO()):
            vault_main()
        self.assertFalse(os.path.exists(tmp_env2))

        # Export-env to file
        exp_file2 = os.path.join(self.temp_dir.name, "out2.env")
        with patch("sys.argv", ["scribe", "--vault", vf, "export-env", exp_file2]), \
             patch("sys.stdout", new=StringIO()):
            vault_main()
        self.assertTrue(os.path.exists(exp_file2))

        # Run without arguments
        with patch("sys.argv", ["scribe", "--vault", vf, "run"]), \
             patch("sys.stderr", new=StringIO()), self.assertRaises(SystemExit):
            vault_main()

        # Set with interactive getpass prompt and mismatched confirm
        with patch("sys.argv", ["scribe", "--vault", vf, "set", "PROMPT_KEY"]), \
             patch("getpass.getpass", side_effect=["pass1", "mismatch"]), \
             patch("sys.stderr", new=StringIO()), self.assertRaises(SystemExit):
            vault_main()

        # Set with interactive getpass prompt matching
        with patch("sys.argv", ["scribe", "--vault", vf, "set", "PROMPT_KEY"]), \
             patch("getpass.getpass", side_effect=["pass1", "pass1"]), \
             patch("sys.stdout", new=StringIO()):
            vault_main()

        # Set existing key updating description without value
        with patch("sys.argv", ["scribe", "--vault", vf, "set", "PROMPT_KEY", "--desc", "Updated Desc"]), \
             patch("sys.stdout", new=StringIO()):
            vault_main()

        # Export-bundle with interactive getpass prompt and mismatched confirm
        with patch("sys.argv", ["scribe", "--vault", vf, "export-bundle", bundle_file]), \
             patch("getpass.getpass", side_effect=["p1", "p2"]), \
             patch("sys.stderr", new=StringIO()), self.assertRaises(SystemExit):
            vault_main()

        # Export-bundle with interactive getpass matching
        with patch("sys.argv", ["scribe", "--vault", vf, "export-bundle", bundle_file]), \
             patch("getpass.getpass", side_effect=["bundlepass", "bundlepass"]), \
             patch("sys.stdout", new=StringIO()):
            vault_main()

        # Import-bundle with interactive getpass
        with patch("sys.argv", ["scribe", "--vault", vf, "import-bundle", bundle_file]), \
             patch("getpass.getpass", return_value="bundlepass"), \
             patch("sys.stdout", new=StringIO()):
            vault_main()

        # General CLI exception handler
        with patch("sys.argv", ["scribe", "--vault", vf, "set", "BAD_KEY", "Val", "--expires-in", "invalid_duration"]), \
             patch("sys.stderr", new=StringIO()), self.assertRaises(SystemExit):
            vault_main()

    def test_16_hardware_fingerprint_fallbacks(self):
        """Verifies fallbacks for unknown OS, macOS hw.model fallback, and Windows WMIC fallback."""
        # Unknown OS
        with patch("platform.system", return_value="FreeBSD"):
            hw_bsd = get_host_hardware_fingerprint()
            self.assertEqual(hw_bsd["os"], "FreeBSD")
            self.assertTrue(hw_bsd["system_uuid_masked"].startswith("NODE..."))

        # Darwin without brand string falling back to hw.model
        with patch("platform.system", return_value="Darwin"), \
             patch("subprocess.check_output", side_effect=[
                 '    "IOPlatformUUID" = "UUID-1234"\n',
                 "",  # empty brand string
                 "MacBookPro18,1\n"  # hw.model
             ]):
            hw_mac = get_host_hardware_fingerprint()
            self.assertIn("Apple Silicon (MacBookPro18,1)", hw_mac["cpu_detail"])

        # Windows PowerShell failure falling back to WMIC
        with patch("platform.system", return_value="Windows"), \
             patch("subprocess.check_output", side_effect=[
                 Exception("No powershell"),
                 "UUID\n11223344-5566-7788-99AA-BBCCDDEEFF00\n",
                 Exception("No cpu")
             ]):
            hw_win = get_host_hardware_fingerprint()
            self.assertEqual(hw_win["system_uuid_masked"], "1122...FF00")

        # Corrupted status check
        corrupt_vf = os.path.join(self.temp_dir.name, "corrupt.enc")
        with open(corrupt_vf, "w") as f:
            f.write("{invalid json")
        cv = ScribeVault(vault_path=corrupt_vf)
        st = cv.status()
        self.assertEqual(st["secrets_count"], -1)

    def test_17_linux_cpuinfo_and_audit_warning(self):
        """Verifies Linux x86 model_name, DMI product UUID, missing cpuinfo, and audit WARNING status."""
        # Absolute date format YYYY-MM-DD
        self.assertIsNotNone(parse_expiry(expires="2026-10-15"))

        # Warning health when expiring soon
        audit_only_warn = ScribeVault(vault_path=os.path.join(self.temp_dir.name, "warn_only.enc"))
        audit_only_warn.set("W_KEY", "V", expires_at=parse_expiry(expires_in="5d"))
        rep_w = audit_only_warn.audit(warn_days=14)
        self.assertEqual(rep_w["health"], "WARNING")

        # x86 cpuinfo with model name
        cpuinfo_x86 = "processor : 0\nmodel name : Intel(R) Core(TM) i7-9700K CPU @ 3.60GHz\nprocessor : 1\n"
        with patch("platform.system", return_value="Linux"), \
             patch("platform.machine", return_value="x86_64"), \
             patch("os.path.exists", side_effect=lambda p: True if p in ["/etc/machine-id", "/proc/cpuinfo", "/sys/class/dmi/id/product_uuid"] else False), \
             patch("builtins.open", mock_open(read_data=cpuinfo_x86)):
            hw_x86 = get_host_hardware_fingerprint()
            self.assertEqual(hw_x86["os"], "Linux")
            self.assertIn("Intel(R) Core(TM) i7-9700K", hw_x86["cpu_detail"])

        # Missing cpuinfo
        with patch("platform.system", return_value="Linux"), \
             patch("platform.machine", return_value="x86_64"), \
             patch("os.path.exists", return_value=False):
            hw_no_info = get_host_hardware_fingerprint()
            self.assertEqual(hw_no_info["os"], "Linux")

        # cpuinfo with only processor count
        with patch("platform.system", return_value="Linux"), \
             patch("platform.machine", return_value="x86_64"), \
             patch("os.path.exists", side_effect=lambda p: True if p in ["/proc/cpuinfo"] else False), \
             patch("builtins.open", mock_open(read_data="processor : 0\n")):
            hw_cores = get_host_hardware_fingerprint()
            self.assertIn("x86_64 (1 cores)", hw_cores["cpu_detail"])

        # cpuinfo open raises OSError
        with patch("platform.system", return_value="Linux"), \
             patch("platform.machine", return_value="x86_64"), \
             patch("os.path.exists", side_effect=lambda p: True if p in ["/proc/cpuinfo"] else False), \
             patch("builtins.open", side_effect=OSError("Read error")):
            hw_err = get_host_hardware_fingerprint()
            self.assertIn("x86_64 Host", hw_err["cpu_detail"])



if __name__ == "__main__":
    unittest.main(verbosity=2)


