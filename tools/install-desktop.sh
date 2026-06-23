#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
pip install -e "$ROOT/bridge"
python3 "$ROOT/hooks/cursor/install.py"
python3 "$ROOT/hooks/claude-code/install.py"
echo "Start bridge: python3 -m bridge --transport websocket --http-port 9876 --ws-port 9877"
echo "Or: ./tools/start_bridge.sh   (start if down)"
echo "Or: ./tools/restart_bridge.sh (kill stale + start)"
echo "Hooks auto-start the bridge on session events when BUDDY_BRIDGE_AUTOSTART=1 (default)."
echo "Phone URL: ws://<your-lan-ip>:9877  (Settings tab in app)"
