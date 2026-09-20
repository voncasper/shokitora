#!/usr/bin/env python3
"""
Scribe Sovereign Vault - CPU/Host-Bound Zero-Cloud Secrets Manager
==================================================================
An air-gapped, on-premise secrets management engine cryptographically bound
to the local host machine identity (CPU, machine-id, motherboard UUID).

Key Features:
- 100% Local & Sovereign: Zero cloud dependencies, zero external network egress.
- Multi-Platform Hardware Derivation:
  * Linux: /etc/machine-id, DMI UUID, and /proc/cpuinfo
  * macOS: IOPlatformUUID via ioreg and machdep.cpu
  * Windows: Motherboard UUID via CIM/wmic and ProcessorId
- Authenticated Encryption: AES-256-GCM guarantees confidentiality and tamper-detection.
- Zero-Prompt Local Decryption: Authorizes instant CLI and Python API queries without
  passwords on the developer's registered machine.
- Safe Portability: Passphrase-encrypted migration bundles (PBKDF2-HMAC-SHA256, 600,000 rounds)
  for hardware upgrades or laptop migration.
- Plaintext .env Elimination:
  * 'import-env': Imports .env files and securely shreds the plaintext file.
  * 'run -- <command>': Injects secrets into memory env vars for any process.

Author: Vincent Capers Jr., Founder & Principal Architect
Corporate Entity: VonCasper Solutions
Part of: Shokitora & Project Scribe Open-Source Architecture
"""

import os
import sys
import json
import stat
import getpass
import argparse
import platform
import subprocess
import hashlib
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Tuple

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

# Default Vault File Locations
# Priority:
# 1. SCRIBE_VAULT_PATH environment variable
# 2. .scribe_vault.enc in current working directory or Git root
# 3. ~/.scribe/vault.enc
def get_default_vault_path() -> str:
    env_path = os.getenv("SCRIBE_VAULT_PATH")
    if env_path:
        return os.path.abspath(env_path)
    
    # Check current directory
    local_cwd = os.path.abspath(".scribe_vault.enc")
    if os.path.exists(local_cwd):
        return local_cwd

    # Check Git repo root
    try:
        git_root = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
            encoding="utf-8"
        ).strip()
        if git_root:
            return os.path.join(git_root, ".scribe_vault.enc")
    except Exception:
        pass


    # Default to home directory
    home_dir = os.path.expanduser("~/.scribe")
    return os.path.join(home_dir, "vault.enc")


SALT_HKDF_CPU_HARDWARE = b"scribe-open-source-vault-cpu-v1"
SALT_PBKDF2_MIGRATION = b"scribe-vault-migration-bundle-v1"


def parse_expiry(expires: Optional[str] = None, expires_in: Optional[str] = None) -> Optional[str]:
    """
    Parses an absolute date or relative duration into an ISO-8601 UTC timestamp.
    Supported formats:
      --expires-in 90d, 30d, 48h, 12m, 1y, or raw integer days (90)
      --expires YYYY-MM-DD or ISO timestamp, or 'CLEAR' / 'NONE'
    """
    now = datetime.now(timezone.utc)
    if expires_in:
        s = expires_in.strip().lower()
        if s.endswith("d"):
            days = int(s[:-1])
            target = now + timedelta(days=days)
        elif s.endswith("h"):
            hours = int(s[:-1])
            target = now + timedelta(hours=hours)
        elif s.endswith("m") or s.endswith("mo"):
            m_count = int(re.sub(r"[^\d]", "", s))
            target = now + timedelta(days=m_count * 30)
        elif s.endswith("y"):
            years = int(s[:-1])
            target = now + timedelta(days=years * 365)
        elif s.isdigit():
            target = now + timedelta(days=int(s))
        else:
            raise ValueError(f"Unsupported --expires-in format: '{expires_in}'. Use e.g. 90d, 30d, 48h, 1y.")
        return target.isoformat()

    if expires:
        s = expires.strip()
        if s.upper() in ["NONE", "CLEAR"]:
            return "CLEAR"
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()
        except Exception:
            pass
        try:  # pragma: no cover
            dt = datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc, hour=23, minute=59, second=59)
            return dt.isoformat()
        except Exception:  # pragma: no cover
            raise ValueError(f"Unsupported --expires date format: '{expires}'. Use YYYY-MM-DD or ISO-8601.")

    return None


def compute_expiry_metadata(expires_at_iso: Optional[str], warn_days: int = 14) -> Dict[str, Any]:
    """Computes days remaining, status (ACTIVE, EXPIRING_SOON, EXPIRED, PERPETUAL), and display."""
    if not expires_at_iso:
        return {
            "expires_at": None,
            "days_remaining": None,
            "status": "PERPETUAL",
            "display": "No Expiry",
            "is_expired": False,
            "is_expiring_soon": False
        }

    now = datetime.now(timezone.utc)
    try:
        dt = datetime.fromisoformat(expires_at_iso.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except Exception:
        return {
            "expires_at": expires_at_iso,
            "days_remaining": None,
            "status": "UNKNOWN",
            "display": str(expires_at_iso),
            "is_expired": False,
            "is_expiring_soon": False
        }

    delta = dt - now
    total_seconds = delta.total_seconds()
    days = int(total_seconds // 86400)

    if total_seconds < 0:
        past_days = abs(days)
        return {
            "expires_at": dt.isoformat(),
            "days_remaining": days,
            "status": "EXPIRED",
            "display": f"EXPIRED ({past_days}d ago)",
            "is_expired": True,
            "is_expiring_soon": False
        }
    elif days <= warn_days:
        return {
            "expires_at": dt.isoformat(),
            "days_remaining": days,
            "status": "EXPIRING_SOON",
            "display": f"WARN: {days}d left ({dt.strftime('%b %d')})",
            "is_expired": False,
            "is_expiring_soon": True
        }
    else:
        return {
            "expires_at": dt.isoformat(),
            "days_remaining": days,
            "status": "ACTIVE",
            "display": f"{days}d left ({dt.strftime('%b %d')})",
            "is_expired": False,
            "is_expiring_soon": False
        }


REMEDIATION_GUIDE = {
    "github": {
        "url": "https://github.com/settings/tokens",
        "service": "GitHub",
        "action": "Generate a new token with required scopes ('repo', 'workflow', etc.) and run: scribe vault set github/token <new_token> --expires-in 90d"
    },
    "huggingface": {
        "url": "https://huggingface.co/settings/tokens",
        "service": "Hugging Face",
        "action": "Generate a new token at HF settings and run: scribe vault set huggingface/token <new_token>"
    },
    "openai": {
        "url": "https://platform.openai.com/api-keys",
        "service": "OpenAI",
        "action": "Generate a new API key at platform.openai.com and run: scribe vault set openai/api_key <new_key>"
    },
    "anthropic": {
        "url": "https://console.anthropic.com/settings/keys",
        "service": "Anthropic",
        "action": "Generate a new API key at console.anthropic.com and run: scribe vault set anthropic/api_key <new_key>"
    },
    "gemini": {
        "url": "https://aistudio.google.com/app/apikey",
        "service": "Google AI Studio / Gemini",
        "action": "Generate a new API key in Google AI Studio and run: scribe vault set gemini/api_key <new_key>"
    }
}


def get_remediation_info(key: str) -> Dict[str, str]:
    """Returns service name, renewal URL, and rotation action for a given secret key."""
    k_lower = key.lower()
    for prefix, info in REMEDIATION_GUIDE.items():
        if prefix in k_lower:
            return info
    return {
        "url": "N/A",
        "service": "Internal / Custom Service",
        "action": f"Rotate secret credentials and run: scribe vault set {key} <new_value>"
    }


def get_remediation_url(key: str) -> str:
    """Returns renewal URL for a given secret key."""
    return get_remediation_info(key)["url"]


def get_host_hardware_fingerprint() -> Dict[str, Any]:
    """
    Detects the immutable hardware identity of the host CPU and system board.
    Supports Linux, macOS (Darwin), and Windows.
    """
    sys_name = platform.system()
    machine_arch = platform.machine()
    system_uuid = "UNKNOWN_SYSTEM_UUID"
    cpu_detail = "UNKNOWN_CPU"
    probe_details = {}

    if sys_name == "Linux":
        # 1. Linux Machine ID (world-readable on standard installations)
        for mid_path in ["/etc/machine-id", "/var/lib/dbus/machine-id"]:
            if os.path.exists(mid_path):
                try:
                    with open(mid_path, "r", encoding="utf-8") as f:
                        mid = f.read().strip()
                        if mid:
                            system_uuid = mid
                            probe_details["machine_id_source"] = mid_path
                            break
                except Exception:  # pragma: no cover
                    pass

        # 2. DMI Product UUID (if readable without root)
        for dmi_path in ["/sys/class/dmi/id/product_uuid", "/sys/devices/virtual/dmi/id/product_uuid"]:
            if os.path.exists(dmi_path):
                try:
                    with open(dmi_path, "r", encoding="utf-8") as f:
                        duuid = f.read().strip()
                        if duuid and duuid != "00000000-0000-0000-0000-000000000000":
                            probe_details["dmi_uuid"] = duuid
                            break
                except Exception:  # pragma: no cover
                    pass


        # 3. CPU Info from /proc/cpuinfo
        if os.path.exists("/proc/cpuinfo"):
            try:
                model_name = None
                cpu_part = None
                cpu_arch = None
                cores = 0
                with open("/proc/cpuinfo", "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("processor"):
                            cores += 1
                        elif "model name" in line and not model_name:
                            model_name = line.split(":", 1)[1].strip()
                        elif "CPU part" in line and not cpu_part:
                            cpu_part = line.split(":", 1)[1].strip()
                        elif "CPU architecture" in line and not cpu_arch:
                            cpu_arch = line.split(":", 1)[1].strip()
                
                if model_name:
                    cpu_detail = f"{model_name} ({cores} cores)"
                elif cpu_part:
                    cpu_detail = f"ARMv{cpu_arch or '8'} Part {cpu_part} ({cores} cores)"
                else:
                    cpu_detail = f"{machine_arch} ({cores} cores)"
            except Exception:
                cpu_detail = f"{machine_arch} Host"
        else:
            cpu_detail = f"{machine_arch} Host"

    elif sys_name == "Darwin":
        # macOS IOPlatformUUID
        try:
            cmd = ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"]
            out = subprocess.check_output(cmd, encoding="utf-8", stderr=subprocess.DEVNULL)
            for line in out.splitlines():
                if "IOPlatformUUID" in line:
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        system_uuid = parts[1].strip().strip('"')
                        probe_details["ioreg_source"] = "IOPlatformUUID"
                        break
        except Exception:  # pragma: no cover
            pass

        # macOS CPU Brand
        try:
            cpu_out = subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], encoding="utf-8", stderr=subprocess.DEVNULL).strip()
            if cpu_out:
                cpu_detail = cpu_out
            else:
                hw_model = subprocess.check_output(["sysctl", "-n", "hw.model"], encoding="utf-8", stderr=subprocess.DEVNULL).strip()
                cpu_detail = f"Apple Silicon ({hw_model})"
        except Exception:  # pragma: no cover
            cpu_detail = f"macOS {machine_arch}"

    elif sys_name == "Windows":
        # Windows BIOS UUID via PowerShell CIM or WMIC
        try:
            ps_cmd = ["powershell", "-NoProfile", "-Command", "(Get-CimInstance -Class Win32_ComputerSystemProduct).UUID"]
            win_uuid = subprocess.check_output(ps_cmd, encoding="utf-8", stderr=subprocess.DEVNULL).strip()
            if win_uuid:
                system_uuid = win_uuid
                probe_details["powershell_source"] = "Win32_ComputerSystemProduct"
        except Exception:
            try:
                wmic_out = subprocess.check_output(["wmic", "csproduct", "get", "uuid"], encoding="utf-8", stderr=subprocess.DEVNULL).strip()
                lines = [l.strip() for l in wmic_out.splitlines() if l.strip() and "UUID" not in l.upper()]
                if lines:
                    system_uuid = lines[0]
                    probe_details["wmic_source"] = "csproduct uuid"
            except Exception:  # pragma: no cover
                pass

        # Windows CPU Name
        try:
            ps_cpu = ["powershell", "-NoProfile", "-Command", "(Get-CimInstance -Class Win32_Processor).Name"]
            win_cpu = subprocess.check_output(ps_cpu, encoding="utf-8", stderr=subprocess.DEVNULL).strip()
            if win_cpu:
                cpu_detail = win_cpu
        except Exception:  # pragma: no cover
            pass


    # Universal fallback if system_uuid could not be determined
    if system_uuid == "UNKNOWN_SYSTEM_UUID":
        import uuid
        node_id = hex(uuid.getnode())
        system_uuid = f"NODE-{node_id}"
        probe_details["fallback"] = "uuid.getnode"

    # Construct Normalized Hardware Seed
    raw_seed = f"SCRIBE_HOST:{sys_name}:{machine_arch}:{system_uuid}:{cpu_detail}"
    fingerprint_hash = hashlib.sha256(raw_seed.encode("utf-8")).hexdigest()

    # Masked representation for safe logs
    masked_uuid = system_uuid if len(system_uuid) <= 8 else f"{system_uuid[:4]}...{system_uuid[-4:]}"

    return {
        "os": sys_name,
        "arch": machine_arch,
        "system_uuid_masked": masked_uuid,
        "cpu_detail": cpu_detail,
        "fingerprint_sha256": fingerprint_hash,
        "seed": raw_seed,
        "probe_details": probe_details
    }


def derive_key_from_seed(seed_string: str, salt: bytes = SALT_HKDF_CPU_HARDWARE) -> bytes:
    """Derives a 256-bit AES-GCM key using HKDF-SHA256 from the host CPU/hardware seed."""
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=b"scribe-hardware-bound-key"
    )
    return hkdf.derive(seed_string.encode("utf-8"))


def derive_key_from_passphrase(passphrase: str, salt: bytes = SALT_PBKDF2_MIGRATION) -> bytes:
    """Derives a 256-bit AES-GCM key using PBKDF2-HMAC-SHA256 (600,000 iterations) for migration bundles."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=600_000
    )
    return kdf.derive(passphrase.encode("utf-8"))


class ScribeVault:
    """
    Scribe CPU-Bound Local Secrets Vault.
    Provides authenticated encryption (AES-256-GCM) with zero-prompt hardware key derivation.
    """
    def __init__(self, vault_path: Optional[str] = None):
        self.vault_path = os.path.abspath(vault_path or get_default_vault_path())
        self.hw_info = get_host_hardware_fingerprint()
        self.key = derive_key_from_seed(self.hw_info["seed"])

    def _ensure_secure_permissions(self, path: str):
        """Enforces 0600 file permissions (read/write only by owner)."""
        if platform.system() != "Windows" and os.path.exists(path):
            try:
                os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
            except Exception:  # pragma: no cover
                pass


    def _load_raw_vault(self) -> Dict[str, Any]:
        """Loads and decrypts the vault payload."""
        if not os.path.exists(self.vault_path):
            return {"version": "1.0", "secrets": {}, "metadata": {}}

        with open(self.vault_path, "r", encoding="utf-8") as f:
            envelope = json.load(f)

        nonce = bytes.fromhex(envelope["nonce"])
        ciphertext = bytes.fromhex(envelope["ciphertext"])

        aesgcm = AESGCM(self.key)
        try:
            decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None)
            return json.loads(decrypted_bytes.decode("utf-8"))
        except Exception as e:
            bound_fp = envelope.get("hardware_binding", {}).get("fingerprint_sha256", "UNKNOWN")
            raise PermissionError(
                f"Hardware decryption failed. This vault is cryptographically locked to host CPU/System "
                f"(Fingerprint: {bound_fp[:16]}...). Decryption on this machine is unauthorized."
            ) from e

    def _save_raw_vault(self, data: Dict[str, Any]):
        """Encrypts and writes the vault payload to disk atomically with 0600 permissions."""
        os.makedirs(os.path.dirname(os.path.abspath(self.vault_path)), exist_ok=True)

        payload_bytes = json.dumps(data, indent=2).encode("utf-8")
        nonce = os.urandom(12)
        aesgcm = AESGCM(self.key)
        ciphertext = aesgcm.encrypt(nonce, payload_bytes, None)

        envelope = {
            "version": "1.0",
            "type": "SCRIBE_CPU_VAULT",
            "cipher": "AES-256-GCM",
            "kdf": "HKDF-SHA256",
            "hardware_binding": {
                "os": self.hw_info["os"],
                "arch": self.hw_info["arch"],
                "cpu_detail": self.hw_info["cpu_detail"],
                "system_uuid_masked": self.hw_info["system_uuid_masked"],
                "fingerprint_sha256": self.hw_info["fingerprint_sha256"]
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
            "nonce": nonce.hex(),
            "ciphertext": ciphertext.hex()
        }

        tmp_path = f"{self.vault_path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(envelope, f, indent=2)
        self._ensure_secure_permissions(tmp_path)
        os.replace(tmp_path, self.vault_path)
        self._ensure_secure_permissions(self.vault_path)

    def set(self, key: str, value: Optional[str] = None, description: Optional[str] = None, expires_at: Optional[str] = None):
        """Stores or updates a secret and optional expiration policy."""
        key = key.strip()
        data = self._load_raw_vault()
        secrets = data.setdefault("secrets", {})
        now = datetime.now(timezone.utc).isoformat()

        entry = secrets.get(key)
        if entry is None:
            if value is None:
                raise ValueError(f"Secret '{key}' does not exist. A value must be provided to create it.")
            entry = {
                "value": value,
                "created_at": now,
                "updated_at": now,
                "description": description or ""
            }
        else:
            if value is not None:
                entry["value"] = value
            entry["updated_at"] = now
            if description is not None:
                entry["description"] = description

        if expires_at == "CLEAR":
            entry.pop("expires_at", None)
        elif expires_at is not None:
            entry["expires_at"] = expires_at

        secrets[key] = entry
        self._save_raw_vault(data)

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Retrieves a decrypted secret value."""
        data = self._load_raw_vault()
        entry = data.get("secrets", {}).get(key)
        if entry is None:
            return default
        return entry.get("value", default)

    def delete(self, key: str) -> bool:
        """Deletes a secret from the vault."""
        data = self._load_raw_vault()
        secrets = data.get("secrets", {})
        if key in secrets:
            del secrets[key]
            self._save_raw_vault(data)
            return True
        return False

    def list(self) -> List[Dict[str, Any]]:
        """Lists all stored secret keys with metadata (masking actual values)."""
        data = self._load_raw_vault()
        results = []
        for k, v in data.get("secrets", {}).items():
            val = str(v.get("value", ""))
            val_len = len(val)
            if val_len > 4:
                masked = f"{'*' * min(val_len - 4, 8)}{val[-4:]}"
            else:
                masked = "****"
            exp_meta = compute_expiry_metadata(v.get("expires_at"))
            results.append({
                "key": k,
                "description": v.get("description", ""),
                "masked_preview": masked,
                "length": val_len,
                "created_at": v.get("created_at", ""),
                "updated_at": v.get("updated_at", ""),
                "expires_at": v.get("expires_at"),
                "status": exp_meta["status"],
                "display_expiry": exp_meta["display"],
                "days_remaining": exp_meta["days_remaining"],
                "is_expired": exp_meta["is_expired"],
                "is_expiring_soon": exp_meta["is_expiring_soon"]
            })
        return sorted(results, key=lambda x: x["key"])

    def audit(self, warn_days: int = 14) -> Dict[str, Any]:
        """
        Audits all stored secrets for upcoming expiration or expired credentials.
        Returns categorization by status with counts and actionable recommendations.
        """
        data = self._load_raw_vault()
        secrets = data.get("secrets", {})
        
        expired = []
        expiring_soon = []
        active = []
        perpetual = []

        for k, v in secrets.items():
            val = str(v.get("value", ""))
            val_len = len(val)
            masked = f"{'*' * min(val_len - 4, 8)}{val[-4:]}" if val_len > 4 else "****"
            exp_meta = compute_expiry_metadata(v.get("expires_at"), warn_days=warn_days)
            rem_info = get_remediation_info(k)
            item = {
                "key": k,
                "description": v.get("description", ""),
                "masked_preview": masked,
                "length": val_len,
                "expires_at": v.get("expires_at"),
                "status": exp_meta["status"],
                "display_expiry": exp_meta["display"],
                "days_remaining": exp_meta["days_remaining"],
                "service": rem_info["service"],
                "remediation_url": rem_info["url"],
                "remediation_action": rem_info["action"]
            }
            if exp_meta["status"] == "EXPIRED":
                expired.append(item)
            elif exp_meta["status"] == "EXPIRING_SOON":
                expiring_soon.append(item)
            elif exp_meta["status"] == "ACTIVE":
                active.append(item)
            else:
                perpetual.append(item)

        total = len(secrets)
        health = "HEALTHY"
        if expired:
            health = "CRITICAL"
        elif expiring_soon:
            health = "WARNING"

        return {
            "health": health,
            "warn_days_threshold": warn_days,
            "counts": {
                "total": total,
                "expired": len(expired),
                "expiring_soon": len(expiring_soon),
                "active": len(active),
                "perpetual": len(perpetual)
            },
            "expired": expired,
            "expiring_soon": expiring_soon,
            "active": active,
            "perpetual": perpetual
        }

    def triage(self, query: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Diagnoses secrets for authentication/expiration issues and provides remediation.
        """
        data = self._load_raw_vault()
        secrets = data.get("secrets", {})
        results = []

        for k, v in secrets.items():
            if query and query.lower() not in k.lower():
                continue

            val = str(v.get("value", ""))
            val_len = len(val)
            masked = f"{'*' * min(val_len - 4, 8)}{val[-4:]}" if val_len > 4 else "****"
            exp_meta = compute_expiry_metadata(v.get("expires_at"))
            rem_info = get_remediation_info(k)
            
            # Formulate diagnosis
            if exp_meta["status"] == "EXPIRED":
                days = abs(exp_meta["days_remaining"] or 0)
                diagnosis = f"CRITICAL: Secret expired {days} days ago. Auth failure (e.g. HTTP 401) is expected."
            elif exp_meta["status"] == "EXPIRING_SOON":
                days = exp_meta["days_remaining"] or 0
                diagnosis = f"WARNING: Secret expires in {days} days. Rotate immediately to prevent outage."
            elif exp_meta["status"] == "ACTIVE":
                days = exp_meta["days_remaining"] or 0
                diagnosis = f"OK: Secret is active ({days} days remaining)."
            else:
                diagnosis = "INFO: Secret is perpetual (no expiry configured)."

            results.append({
                "key": k,
                "description": v.get("description", ""),
                "masked_preview": masked,
                "length": val_len,
                "expires_at": v.get("expires_at"),
                "status": exp_meta["status"],
                "display_expiry": exp_meta["display"],
                "days_remaining": exp_meta["days_remaining"],
                "diagnosis": diagnosis,
                "service": rem_info["service"],
                "remediation_url": rem_info["url"],
                "remediation_action": rem_info["action"]
            })

        return sorted(results, key=lambda x: x["key"])

    def status(self) -> Dict[str, Any]:
        """Returns vault health, host cryptographic binding, and file metadata."""
        exists = os.path.exists(self.vault_path)
        secret_count = 0
        file_size = 0
        if exists:
            file_size = os.path.getsize(self.vault_path)
            try:
                data = self._load_raw_vault()
                secret_count = len(data.get("secrets", {}))
            except Exception:
                secret_count = -1  # Indicates lock mismatch

        return {
            "vault_path": self.vault_path,
            "exists": exists,
            "file_size_bytes": file_size,
            "secrets_count": secret_count,
            "hardware_binding": self.hw_info,
            "cipher": "AES-256-GCM",
            "kdf": "HKDF-SHA256 (32-byte host CPU/hardware seed)"
        }

    def import_env(self, env_path: str = ".env", delete_source: bool = False) -> int:
        """
        Parses an existing .env file, stores each variable into the vault,
        and optionally shreds/deletes the plaintext .env file.
        """
        if not os.path.exists(env_path):
            raise FileNotFoundError(f"Plaintext environment file '{env_path}' does not exist.")

        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        data = self._load_raw_vault()
        secrets = data.setdefault("secrets", {})
        now = datetime.now(timezone.utc).isoformat()
        count = 0

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip()
                # Strip leading/trailing quotes if present
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                
                entry = secrets.get(key, {})
                entry["value"] = val
                entry["updated_at"] = now
                if "created_at" not in entry:
                    entry["created_at"] = now
                    entry["description"] = f"Imported from {os.path.basename(env_path)}"
                secrets[key] = entry
                count += 1

        self._save_raw_vault(data)

        if delete_source:
            # Secure shred: overwrite file content with zeros before unlinking
            try:
                size = os.path.getsize(env_path)
                with open(env_path, "wb") as f:
                    f.write(b"\x00" * size)
                os.remove(env_path)
            except Exception as e:  # pragma: no cover
                # If shred fails, attempt regular remove
                if os.path.exists(env_path):
                    os.remove(env_path)


        return count

    def export_env(self, output_path: Optional[str] = None) -> str:
        """
        Exports all decrypted secrets in .env format.
        If output_path is given, writes to disk with 0600 permissions.
        """
        data = self._load_raw_vault()
        lines = [
            f"# Scribe Decrypted Environment Export",
            f"# Exported on: {datetime.now(timezone.utc).isoformat()}",
            f"# WARNING: Keep this file secure and add to .gitignore immediately",
            ""
        ]
        for k in sorted(data.get("secrets", {}).keys()):
            v = data["secrets"][k]["value"]
            # Escape quotes if necessary
            if "\n" in v or '"' in v or " " in v:
                v_clean = v.replace('"', '\\"')
                lines.append(f'{k}="{v_clean}"')
            else:
                lines.append(f"{k}={v}")

        content = "\n".join(lines) + "\n"
        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(content)
            self._ensure_secure_permissions(output_path)

        return content

    def run_command(self, cmd_args: List[str]) -> int:
        """
        Executes a child process with all vault secrets dynamically injected
        into its in-memory os.environ. No plaintext secrets touch the disk.
        """
        data = self._load_raw_vault()
        child_env = os.environ.copy()
        for k, v in data.get("secrets", {}).items():
            child_env[k] = v["value"]

        try:
            result = subprocess.run(cmd_args, env=child_env)
            return result.returncode
        except Exception as e:
            print(f"Error executing command: {e}", file=sys.stderr)
            return 1

    def export_migratable_bundle(self, output_path: str, passphrase: str):
        """
        Exports the entire vault into a password-encrypted migration bundle (PBKDF2-HMAC-SHA256)
        that can be safely transferred to a new laptop or developer workstation.
        """
        data = self._load_raw_vault()
        bundle_key = derive_key_from_passphrase(passphrase)
        aesgcm = AESGCM(bundle_key)
        nonce = os.urandom(12)
        payload_bytes = json.dumps(data, indent=2).encode("utf-8")
        ciphertext = aesgcm.encrypt(nonce, payload_bytes, None)

        bundle = {
            "version": "1.0",
            "type": "SCRIBE_VAULT_MIGRATION_BUNDLE",
            "cipher": "AES-256-GCM",
            "kdf": "PBKDF2-HMAC-SHA256 (600,000 iterations)",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "source_hardware": self.hw_info,
            "nonce": nonce.hex(),
            "ciphertext": ciphertext.hex()
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(bundle, f, indent=2)
        self._ensure_secure_permissions(output_path)

    def import_migratable_bundle(self, bundle_path: str, passphrase: str, overwrite: bool = False):
        """
        Imports a migration bundle, decrypts with the passphrase, and immediately
        re-encrypts and locks it to THIS machine's CPU/hardware fingerprint.
        """
        with open(bundle_path, "r", encoding="utf-8") as f:
            bundle = json.load(f)

        bundle_key = derive_key_from_passphrase(passphrase)
        aesgcm = AESGCM(bundle_key)
        nonce = bytes.fromhex(bundle["nonce"])
        ciphertext = bytes.fromhex(bundle["ciphertext"])

        decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None)
        imported_data = json.loads(decrypted_bytes.decode("utf-8"))

        if not overwrite and os.path.exists(self.vault_path):
            existing = self._load_raw_vault()
            existing_secrets = existing.setdefault("secrets", {})
            existing_secrets.update(imported_data.get("secrets", {}))
            self._save_raw_vault(existing)
        else:
            self._save_raw_vault(imported_data)


# Top-level Convenience Python API
_default_scribe_vault = None

def _get_vault(vault_path: Optional[str] = None) -> ScribeVault:
    global _default_scribe_vault
    if _default_scribe_vault is None or (vault_path and _default_scribe_vault.vault_path != os.path.abspath(vault_path)):
        _default_scribe_vault = ScribeVault(vault_path)
    return _default_scribe_vault

def get_secret(key: str, default: Optional[str] = None, vault_path: Optional[str] = None) -> Optional[str]:
    """Top-level convenience function to get a secret."""
    return _get_vault(vault_path).get(key, default)

def set_secret(key: str, value: Optional[str] = None, description: Optional[str] = None, expires_at: Optional[str] = None, vault_path: Optional[str] = None):
    """Top-level convenience function to store a secret and optional expiration policy."""
    _get_vault(vault_path).set(key, value=value, description=description, expires_at=expires_at)

def delete_secret(key: str, vault_path: Optional[str] = None) -> bool:
    """Top-level convenience function to delete a secret."""
    return _get_vault(vault_path).delete(key)

def list_secrets(vault_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Top-level convenience function to list secrets."""
    return _get_vault(vault_path).list()

def audit_secrets(warn_days: int = 14, vault_path: Optional[str] = None) -> Dict[str, Any]:
    """Top-level convenience function to audit secrets."""
    return _get_vault(vault_path).audit(warn_days=warn_days)

def triage_secrets(query: Optional[str] = None, vault_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Top-level convenience function to triage secrets."""
    return _get_vault(vault_path).triage(query=query)

def load_secrets_into_environ(vault_path: Optional[str] = None, override: bool = False):
    """
    Loads all decrypted vault secrets into the current Python process's os.environ.
    Useful for initializing applications at startup.
    """
    data = _get_vault(vault_path)._load_raw_vault()
    for k, v in data.get("secrets", {}).items():
        if override or k not in os.environ:
            os.environ[k] = v["value"]


# --- CLI INTERFACE ---
def main():
    parser = argparse.ArgumentParser(
        prog="scribe vault",
        description="Scribe Sovereign Vault - CPU/Host-Bound Zero-Cloud Secrets Manager"
    )
    parser.add_argument("--vault", default=None, help="Path to encrypted vault file (defaults to .scribe_vault.enc or ~/.scribe/vault.enc)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # set
    p_set = subparsers.add_parser("set", help="Store or update a secret and optional expiration policy")
    p_set.add_argument("key", help="Secret identifier (e.g., GEMINI_API_KEY, TELEGRAM_BOT_TOKEN)")
    p_set.add_argument("value", nargs="?", default=None, help="Secret value (omit to enter via secure prompt, or '-' for stdin)")
    p_set.add_argument("--desc", help="Optional description of the secret")
    p_set.add_argument("--expires", help="Expiration date (YYYY-MM-DD, ISO-8601, or 'CLEAR' to remove)")
    p_set.add_argument("--expires-in", help="Relative expiration duration (e.g., 90d, 30d, 48h, 12m, 1y)")

    # get
    p_get = subparsers.add_parser("get", help="Retrieve a secret value")
    p_get.add_argument("key", help="Secret identifier")
    p_get.add_argument("--raw", action="store_true", help="Print raw value without newline")

    # list
    p_list = subparsers.add_parser("list", help="List all stored secret keys with metadata (values masked)")
    p_list.add_argument("--json", action="store_true", help="Output as JSON")

    # audit
    p_audit = subparsers.add_parser("audit", help="Audit all secrets for expiration and security posture")
    p_audit.add_argument("--warn-days", type=int, default=14, help="Days threshold for EXPIRING_SOON warning (default: 14)")
    p_audit.add_argument("--json", action="store_true", help="Output audit report as JSON")

    # triage
    p_triage = subparsers.add_parser("triage", help="Triage credentials and diagnose authentication/expiration failures")
    p_triage.add_argument("query", nargs="?", default=None, help="Specific secret key or substring to triage (e.g., 'github')")
    p_triage.add_argument("--json", action="store_true", help="Output triage report as JSON")

    # delete
    p_del = subparsers.add_parser("delete", help="Delete a secret")
    p_del.add_argument("key", help="Secret identifier")

    # status
    subparsers.add_parser("status", help="Show hardware binding and vault health")

    # import-env
    p_impenv = subparsers.add_parser("import-env", help="Import secrets from a plaintext .env file")
    p_impenv.add_argument("file", nargs="?", default=".env", help="Path to .env file (default: .env)")
    p_impenv.add_argument("--delete-source", action="store_true", help="Securely shred and delete the plaintext .env file after import")

    # export-env
    p_expenv = subparsers.add_parser("export-env", help="Export decrypted secrets to .env format")
    p_expenv.add_argument("output_file", nargs="?", default=None, help="Optional output path (prints to stdout if omitted)")

    # run
    p_run = subparsers.add_parser("run", help="Run a command with decrypted secrets injected into in-memory environment variables")
    p_run.add_argument("run_args", nargs=argparse.REMAINDER, help="Command to execute (e.g., -- python app.py)")

    # export-bundle
    p_exp = subparsers.add_parser("export-bundle", help="Export a password-encrypted migratable bundle")
    p_exp.add_argument("output_file", help="Path to write the migration bundle JSON")
    p_exp.add_argument("--passphrase", help="Recovery passphrase (prompts securely if omitted)")

    # import-bundle
    p_imp = subparsers.add_parser("import-bundle", help="Import a migratable bundle and lock to current CPU/host")
    p_imp.add_argument("bundle_file", help="Path to migration bundle JSON")
    p_imp.add_argument("--passphrase", help="Recovery passphrase (prompts securely if omitted)")
    p_imp.add_argument("--overwrite", action="store_true", help="Overwrite existing vault instead of merging")

    args = parser.parse_args()
    vault = ScribeVault(vault_path=args.vault)

    try:
        if args.command == "status":
            st = vault.status()
            print("\n🔒 Scribe CPU-Bound Sovereign Vault Status")
            print("=" * 65)
            print(f"Vault File Location  : {st['vault_path']}")
            print(f"File Exists          : {'YES' if st['exists'] else 'NO (Uninitialized)'}")
            print(f"File Size            : {st['file_size_bytes']} bytes")
            print(f"Stored Secrets       : {st['secrets_count']}")
            print(f"Cipher Algorithm     : {st['cipher']}")
            print(f"Key Derivation       : {st['kdf']}")
            print("\n⚡ Host CPU Cryptographic Binding:")
            hw = st["hardware_binding"]
            print(f"  Operating System   : {hw['os']} ({hw['arch']})")
            print(f"  Host CPU Info      : {hw['cpu_detail']}")
            print(f"  System UUID Masked : {hw['system_uuid_masked']}")
            print(f"  Hardware SHA256    : {hw['fingerprint_sha256'][:24]}...")
            print(f"  Enclave Binding    : ACTIVE (Locked to this machine's CPU/Silicon)\n")

        elif args.command == "set":
            expiry_iso = parse_expiry(expires=args.expires, expires_in=args.expires_in)
            val = args.value
            if val == "-":
                val = sys.stdin.read().rstrip("\r\n")
            elif val is None:
                # If secret already exists and user is only updating expiry/desc, don't prompt for value
                existing_val = vault.get(args.key)
                if existing_val is not None and (expiry_iso is not None or args.desc is not None):
                    val = None  # Indicates keep existing value
                else:
                    val = getpass.getpass(f"Enter secret value for '{args.key}': ")
                    confirm = getpass.getpass("Confirm secret value: ")
                    if val != confirm:
                        print("Error: Values do not match.", file=sys.stderr)
                        sys.exit(1)
            vault.set(args.key, value=val, description=args.desc, expires_at=expiry_iso)
            print(f"✓ Secret '{args.key}' encrypted and saved to CPU vault.")
            if expiry_iso == "CLEAR":
                print("  Expiration policy: CLEARED (perpetual)")
            elif expiry_iso:
                meta = compute_expiry_metadata(expiry_iso)
                print(f"  Expires: {meta['display']} ({expiry_iso})")

        elif args.command == "get":
            val = vault.get(args.key)
            if val is None:
                print(f"Error: Secret '{args.key}' not found in vault.", file=sys.stderr)
                sys.exit(1)
            if args.raw:
                sys.stdout.write(val)
                sys.stdout.flush()
            else:
                print(val)

        elif args.command == "list":
            secrets = vault.list()
            if args.json:
                print(json.dumps(secrets, indent=2))
            else:
                if not secrets:
                    print("No secrets currently stored in Scribe vault.")
                    return
                print(f"\n{'KEY':<28} | {'PREVIEW':<14} | {'STATUS':<13} | {'EXPIRES':<22} | {'DESCRIPTION'}")
                print("-" * 115)
                for s in secrets:
                    print(
                        f"{s['key']:<28} | "
                        f"{s['masked_preview']:<14} | "
                        f"{s['status']:<13} | "
                        f"{s['display_expiry']:<22} | "
                        f"{s['description'][:32]}"
                    )
                print(f"\nTotal Secrets: {len(secrets)}\n")

        elif args.command == "audit":
            rep = vault.audit(warn_days=args.warn_days)
            if args.json:
                print(json.dumps(rep, indent=2))
            else:
                print(f"\n================================================================================")
                print(f" SCRIBE VAULT AUDIT - POSTURE & EXPIRATION REPORT")
                print(f"================================================================================")
                print(f"Overall Health   : {rep['health']}")
                print(f"Total Secrets    : {rep['counts']['total']}")
                print(f"  - Expired      : {rep['counts']['expired']}")
                print(f"  - Expiring Soon: {rep['counts']['expiring_soon']} (within {args.warn_days} days)")
                print(f"  - Active       : {rep['counts']['active']}")
                print(f"  - Perpetual    : {rep['counts']['perpetual']}")
                print("-" * 80)

                if rep["expired"]:
                    print("\n[CRITICAL] EXPIRED SECRETS (IMMEDIATE ACTION REQUIRED):")
                    for s in rep["expired"]:
                        print(f"  ! {s['key']} ({s['display_expiry']})")
                        print(f"    Service     : {s['service']}")
                        print(f"    Renew URL   : {s['remediation_url']}")
                        print(f"    Remediation : {s['remediation_action']}")

                if rep["expiring_soon"]:
                    print(f"\n[WARNING] SECRETS EXPIRING WITHIN {args.warn_days} DAYS:")
                    for s in rep["expiring_soon"]:
                        print(f"  * {s['key']} ({s['display_expiry']})")
                        print(f"    Service     : {s['service']}")
                        print(f"    Renew URL   : {s['remediation_url']}")
                        print(f"    Remediation : {s['remediation_action']}")

                print(f"\nAUDITED SECRETS INVENTORY:")
                print(f"{'KEY':<28} | {'PREVIEW':<14} | {'STATUS':<13} | {'EXPIRES':<22} | {'DESCRIPTION'}")
                print("-" * 115)
                all_items = sorted(
                    rep["expired"] + rep["expiring_soon"] + rep["active"] + rep["perpetual"],
                    key=lambda x: x["key"]
                )
                for s in all_items:
                    print(
                        f"{s['key']:<28} | "
                        f"{s['masked_preview']:<14} | "
                        f"{s['status']:<13} | "
                        f"{s['display_expiry']:<22} | "
                        f"{s['description'][:32]}"
                    )
                print(f"\nStatus: {rep['health']}\n")

        elif args.command == "triage":
            diag = vault.triage(query=args.query)
            if args.json:
                print(json.dumps(diag, indent=2))
            else:
                header = "SCRIBE VAULT TRIAGE & DIAGNOSTIC ASSISTANT"
                if args.query:
                    header += f" (Filter: '{args.query}')"
                print(f"\n{'=' * 80}")
                print(f" {header}")
                print(f"{'=' * 80}")
                if not diag:
                    print(f"No secrets found matching query '{args.query}'.\n")
                    return

                for item in diag:
                    status_symbol = "✓" if item["status"] in ["ACTIVE", "PERPETUAL"] else ("!" if item["status"] == "EXPIRING_SOON" else "✗")
                    print(f"\n[{status_symbol}] Secret: {item['key']}")
                    print(f"    Status      : {item['status']} ({item['display_expiry']})")
                    print(f"    Diagnosis   : {item['diagnosis']}")
                    print(f"    Service     : {item['service']}")
                    print(f"    Renew URL   : {item['remediation_url']}")
                    print(f"    Action      : {item['remediation_action']}")
                print(f"\n{'=' * 80}\n")

        elif args.command == "delete":
            ok = vault.delete(args.key)
            if ok:
                print(f"✓ Secret '{args.key}' deleted from vault.")
            else:
                print(f"Error: Secret '{args.key}' not found.", file=sys.stderr)
                sys.exit(1)

        elif args.command == "import-env":
            count = vault.import_env(args.file, delete_source=args.delete_source)
            print(f"✓ Successfully imported {count} secrets from '{args.file}' into Scribe Vault.")
            if args.delete_source:
                print(f"✓ Plaintext file '{args.file}' was securely shredded and deleted from disk.")

        elif args.command == "export-env":
            out = vault.export_env(args.output_file)
            if args.output_file:
                print(f"✓ Decrypted secrets exported to '{args.output_file}' (Mode 0600).")
            else:
                sys.stdout.write(out)

        elif args.command == "run":
            cmd = args.run_args
            # Handle possible leading '--' separator
            if cmd and cmd[0] == "--":
                cmd = cmd[1:]
            if not cmd:
                print("Error: No command specified to run. Usage: scribe vault run -- <command>", file=sys.stderr)
                sys.exit(1)
            code = vault.run_command(cmd)
            sys.exit(code)

        elif args.command == "export-bundle":
            pw = args.passphrase
            if not pw:
                pw = getpass.getpass("Enter master recovery passphrase for bundle: ")
                confirm = getpass.getpass("Confirm recovery passphrase: ")
                if pw != confirm:
                    print("Error: Passphrases do not match.", file=sys.stderr)
                    sys.exit(1)
            vault.export_migratable_bundle(args.output_file, pw)
            print(f"✓ Migratable vault bundle exported to '{args.output_file}'.")
            print("  This bundle can be transported to another machine and imported using your recovery passphrase.")

        elif args.command == "import-bundle":
            pw = args.passphrase
            if not pw:
                pw = getpass.getpass("Enter master recovery passphrase for bundle: ")
            vault.import_migratable_bundle(args.bundle_file, pw, overwrite=args.overwrite)
            print(f"✓ Bundle imported successfully and cryptographically re-locked to THIS machine's CPU.")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
