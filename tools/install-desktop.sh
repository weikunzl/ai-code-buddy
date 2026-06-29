#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
pip install -e "$ROOT/bridge"
python3 "$ROOT/hooks/cursor/install.py"
python3 "$ROOT/hooks/claude-code/install.py"
python3 "$ROOT/hooks/trae/install.py"    # global ~/.trae-cn/hooks.json
echo "Start bridge: python3 -m bridge --transport websocket --http-port 19876 --ws-port 19877"
echo "Or: ./tools/start_bridge.sh   (start if down)"
echo "Or: ./tools/restart_bridge.sh (kill stale + start)"
echo "Hooks auto-start the bridge on session events when BUDDY_BRIDGE_AUTOSTART=1 (default)."
echo "Phone URL: ws://<your-lan-ip>:19877  (Settings tab in app)"
