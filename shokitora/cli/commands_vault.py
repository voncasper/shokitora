#!/usr/bin/env python3
"""
CLI entrypoint for Scribe / Shokitora Sovereign Vault
=====================================================
"""
import sys
from shokitora.core.vault import main as vault_main

def main():
    vault_main()

if __name__ == "__main__":
    main()
