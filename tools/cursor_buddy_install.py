#!/usr/bin/env python3
"""Backward-compatible wrapper for hooks.cursor.install."""
from hooks.cursor.install import main

if __name__ == "__main__":
    raise SystemExit(main())
