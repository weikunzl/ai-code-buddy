#!/usr/bin/env python3
"""Backward-compatible wrapper for hooks.cursor.hook."""
from hooks.cursor.hook import *  # noqa: F403
from hooks.cursor.hook import main

if __name__ == "__main__":
    raise SystemExit(main())
