#!/usr/bin/env bash
# Start bridge with USB serial → firmware. Safe in Warp (no Bluetooth API).
#
# Usage:
#   ./tools/start_bridge_serial.sh
#   ./tools/start_bridge_serial.sh /dev/cu.usbmodem2101
#
# Trae/Cursor hooks POST to http://127.0.0.1:19876 — keep BUDDY_BRIDGE_AUTOSTART=0
# so hooks do not spawn a competing websocket bridge.
set -euo pipefail
ROOT="${DEVPET_PACKAGE_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
HTTP_PORT="${BUDDY_HTTP_PORT:-19876}"
VENV="${ROOT}/.venv-session-bridge/bin/python"

if [ ! -x "$VENV" ]; then
  echo "[serial] missing venv: $VENV" >&2
  exit 1
fi

PORT="${1:-}"
if [ -z "$PORT" ]; then
  for pattern in /dev/cu.usbmodem* /dev/tty.usbmodem*; do
    for p in $pattern; do
      [ -e "$p" ] || continue
      PORT="$p"
      break 2
    done
  done
fi
if [ -z "$PORT" ]; then
  echo "[serial] no USB device — plug in StickS3 and retry" >&2
  exit 1
fi

# Optional: stop launchd agent if it keeps restarting --transport ble (crashes in TCC).
if [ "${BUDDY_STOP_LAUNCHD:-1}" = "1" ]; then
  launchctl bootout "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.kunwei.claude-buddy-bridge.plist" 2>/dev/null || true
fi

pkill -f '[P]ython.*-m bridge' 2>/dev/null || true
sleep 0.5
if lsof -ti "tcp:${HTTP_PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "[serial] port ${HTTP_PORT} still in use — stop other bridge first" >&2
  lsof -i "tcp:${HTTP_PORT}" -sTCP:LISTEN 2>/dev/null || true
  exit 1
fi

export DEVPET_PACKAGE_ROOT="$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export BUDDY_BRIDGE_AUTOSTART=0

echo "[serial] ${PORT} → firmware, HTTP :${HTTP_PORT}"
echo "[serial] Ctrl+C to stop; do NOT run bleak/BLE scan in Warp (TCC abort)"
exec "$VENV" -m bridge --transport serial --serial-port "$PORT" --http-port "$HTTP_PORT"
