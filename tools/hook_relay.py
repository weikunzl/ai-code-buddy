#!/usr/bin/env python3
"""Backward-compatible wrapper for hooks.common.relay."""
from hooks.common.relay import *  # noqa: F403
from hooks.common.relay import main

if __name__ == "__main__":
    raise SystemExit(main())
