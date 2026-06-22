#!/usr/bin/env bash
# Stop stale buddy bridges on 9876/9877 and start one process with HTTP + WebSocket.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HTTP_PORT="${BUDDY_HTTP_PORT:-9876}"
WS_PORT="${BUDDY_WS_PORT:-9877}"

stop_port() {
  local port="$1"
  local pids
  pids="$(lsof -ti tcp:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    echo "[stop] port $port -> kill $pids"
    kill $pids 2>/dev/null || true
    sleep 0.5
  fi
}

stop_port "$HTTP_PORT"
stop_port "$WS_PORT"

echo "[start] python3 -m bridge --transport websocket --http-port $HTTP_PORT --ws-port $WS_PORT"
cd "$ROOT"
exec python3 -m bridge --transport websocket --http-port "$HTTP_PORT" --ws-port "$WS_PORT"
