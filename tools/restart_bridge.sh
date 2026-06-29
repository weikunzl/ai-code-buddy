#!/usr/bin/env bash
# Stop stale buddy bridges on 19876/19877 and start one process with HTTP + WebSocket.
set -euo pipefail
ROOT="${DEVPET_PACKAGE_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
HTTP_PORT="${BUDDY_HTTP_PORT:-19876}"
WS_PORT="${BUDDY_WS_PORT:-19877}"
RESTART_LOCK="$ROOT/.buddy/bridge-restarting"

collect_listener_pids() {
  {
    lsof -ti "tcp:${HTTP_PORT}" -sTCP:LISTEN 2>/dev/null || true
    lsof -ti "tcp:${WS_PORT}" -sTCP:LISTEN 2>/dev/null || true
  } | sort -u
}

ports_are_free() {
  ! lsof -ti "tcp:${HTTP_PORT}" -sTCP:LISTEN >/dev/null 2>&1 \
    && ! lsof -ti "tcp:${WS_PORT}" -sTCP:LISTEN >/dev/null 2>&1
}

kill_bridge_processes() {
  pkill -TERM -f '[P]ython.*-m bridge' 2>/dev/null || true
  pkill -TERM -f '[p]ython3 -m bridge' 2>/dev/null || true
}

force_kill_bridge_processes() {
  pkill -9 -f '[P]ython.*-m bridge' 2>/dev/null || true
  pkill -9 -f '[p]ython3 -m bridge' 2>/dev/null || true
}

stop_all_listeners() {
  local attempt pids
  kill_bridge_processes
  for attempt in $(seq 1 16); do
    if ports_are_free; then
      return 0
    fi
    pids="$(collect_listener_pids | tr '\n' ' ')"
    pids="${pids%% }"
    if [[ -z "${pids// /}" ]]; then
      sleep 0.15
      continue
    fi
    if (( attempt >= 3 )); then
      echo "[stop] force kill $pids"
      kill -9 $pids 2>/dev/null || true
      force_kill_bridge_processes
    else
      echo "[stop] kill $pids"
      kill $pids 2>/dev/null || true
      kill_bridge_processes
    fi
    sleep 0.25
  done
  if ports_are_free; then
    return 0
  fi
  echo "[stop] ports ${HTTP_PORT}/${WS_PORT} still in use after cleanup" >&2
  lsof -i "tcp:${HTTP_PORT}" -sTCP:LISTEN 2>/dev/null || true
  lsof -i "tcp:${WS_PORT}" -sTCP:LISTEN 2>/dev/null || true
  return 1
}

cleanup() {
  rm -f "$RESTART_LOCK"
}

mkdir -p "$ROOT/.buddy"
touch "$RESTART_LOCK"
trap cleanup EXIT INT TERM

stop_all_listeners
force_kill_bridge_processes
sleep 0.15
if ! ports_are_free; then
  echo "[stop] could not free ports ${HTTP_PORT}/${WS_PORT}" >&2
  exit 1
fi

start_bridge() {
  python3 -m bridge --transport websocket --http-port "$HTTP_PORT" --ws-port "$WS_PORT"
}

echo "[start] python3 -m bridge --transport websocket --http-port $HTTP_PORT --ws-port $WS_PORT"
cd "$ROOT"
export DEVPET_PACKAGE_ROOT="$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

for attempt in $(seq 1 5); do
  if ! ports_are_free; then
    echo "[start] retry $attempt: ports busy, stopping listeners again" >&2
    stop_all_listeners || true
    force_kill_bridge_processes
    sleep 0.2
  fi
  if start_bridge; then
    exit 0
  fi
  echo "[start] attempt $attempt failed" >&2
  force_kill_bridge_processes
  sleep 0.3
done

echo "[start] bridge failed to bind after retries" >&2
exit 1
