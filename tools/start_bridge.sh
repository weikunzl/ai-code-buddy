#!/usr/bin/env bash
# Start bridge only when ports are free; never kills existing listeners.
set -euo pipefail
ROOT="${DEVPET_PACKAGE_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
export DEVPET_PACKAGE_ROOT="$ROOT"
exec python3 "$ROOT/tools/ensure_bridge.py"
