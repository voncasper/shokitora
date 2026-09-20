"""
Shokitora (書記虎) - The Sovereign Tiger Scribe & Agentic Release Control Plane
==============================================================================
A Git-native memory ledger, CPU-bound sovereign secrets manager, and atomic
CTP release control plane for autonomous AI coding agents and human engineers.

Author: Vincent Capers Jr., Founder & Principal Architect
Corporate Entity: VonCasper Solutions
License: MIT / Apache 2.0 Dual License
"""

__version__ = "0.1.2"
__author__ = "Vincent Capers Jr. (VonCasper Solutions)"

from shokitora.core.vault import (
    ScribeVault,
    get_secret,
    set_secret,
    delete_secret,
    list_secrets,
    audit_secrets,
    triage_secrets,
    parse_expiry,
    compute_expiry_metadata,
    load_secrets_into_environ,
    get_host_hardware_fingerprint,
)

__all__ = [
    "__version__",
    "ScribeVault",
    "get_secret",
    "set_secret",
    "delete_secret",
    "list_secrets",
    "audit_secrets",
    "triage_secrets",
    "parse_expiry",
    "compute_expiry_metadata",
    "load_secrets_into_environ",
    "get_host_hardware_fingerprint",
]
