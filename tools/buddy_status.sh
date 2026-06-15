#!/usr/bin/env bash
# Quick health check for the claude-buddy session bridge.
#
# Reports four facts:
#   1. bridge process alive?
#   2. bridge HTTP responding on 127.0.0.1:$PORT ?
#   3. round-trip a no-op hook payload through hook_relay --strict
#   4. BLE: connection state inferred from bridge log (no scan in this shell)
#
# Why we don't scan BLE here by default:
#   macOS 26 TCC checks the *responsible* process's Info.plist for
#   NSBluetoothAlwaysUsageDescription. Terminals like Warp don't declare it
#   and CoreBluetooth SIGABRTs any python launched from them. The launchd
#   agent that runs session_bridge.py has a different responsible chain
#   (launchd → bridge) and is granted BT permission once. So we let the
#   bridge be the only thing that touches CoreBluetooth, and we read its
#   log here. Use `--scan` if you really want this shell to scan (only
#   safe from Cursor/Terminal.app/iTerm that already have BT permission).
#
# Exit code: 0 if 1+2+3 all green; non-zero otherwise.

set -u
PORT="${BRIDGE_HTTP_PORT:-9876}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PY="${PROJECT_ROOT}/.venv-session-bridge/bin/python"
RELAY="${PROJECT_ROOT}/tools/hook_relay.py"
PYBIN="${PYTHON:-/usr/bin/env python3}"
BRIDGE_LOG="${BRIDGE_LOG:-/tmp/bridge.log}"

DO_SCAN=0
for arg in "$@"; do
  case "$arg" in
    --scan|--ble) DO_SCAN=1 ;;
    --no-ble)     DO_SCAN=0 ;;  # back-compat, no-op (it's already the default)
  esac
done

red()   { printf "\033[31m%s\033[0m" "$1"; }
grn()   { printf "\033[32m%s\033[0m" "$1"; }
ylw()   { printf "\033[33m%s\033[0m" "$1"; }

fail=0

printf "1. bridge process: "
PIDS=$(pgrep -f "session_bridge.py" || true)
if [ -n "$PIDS" ]; then
  printf "%s\n" "$(grn "✓") $(echo "$PIDS" | head -1 | awk '{print "PID="$1}')"
else
  printf "%s\n" "$(red "✗") not running"
  fail=1
fi

printf "2. HTTP %s: " "$PORT"
code=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 3 \
  -X POST -H 'content-type: application/json' -d '{}' \
  "http://127.0.0.1:${PORT}" 2>/dev/null || echo "000")
if [ "$code" = "200" ]; then
  printf "%s\n" "$(grn "✓") HTTP $code"
else
  printf "%s\n" "$(red "✗") HTTP $code"
  fail=1
fi

printf "3. hook_relay --strict: "
payload='{"hook_event_name":"UserPromptSubmit","session_id":"s_status","cwd":"'"${PROJECT_ROOT}"'","prompt":"buddy_status healthcheck"}'
relay_out=$(printf '%s' "$payload" | $PYBIN "$RELAY" --strict 2>&1)
relay_rc=$?
if [ "$relay_rc" = "0" ]; then
  printf "%s\n" "$(grn "✓") exit=0  out=${relay_out}"
else
  printf "%s\n" "$(red "✗") exit=$relay_rc  out=${relay_out}"
  fail=1
fi

# 4. BLE connection state — derived from bridge log, no scan in this shell.
printf "4. BLE state: "
if [ ! -r "$BRIDGE_LOG" ]; then
  printf "%s\n" "$(ylw "?") bridge log not readable ($BRIDGE_LOG)"
else
  # Find the most recent [ble] event. tail to keep this O(1).
  last_ble=$(tail -n 200 "$BRIDGE_LOG" 2>/dev/null | grep -E '^\[ble\]' | tail -n 1 || true)
  if [ -z "$last_ble" ]; then
    printf "%s\n" "$(ylw "?") no [ble] events in log yet (bridge may be transport=serial or just started)"
  else
    case "$last_ble" in
      *"connected "*)
        # e.g. [ble] connected Claude-8E15 @ AA:BB:...
        dev=$(printf "%s" "$last_ble" | sed -n 's/^\[ble\] connected //p')
        printf "%s\n" "$(grn "✓") connected: $dev"
        ;;
      *"disconnected"*)
        printf "%s\n" "$(ylw "○") disconnected — bridge will rescan automatically"
        ;;
      *"no device found"*|*"scanning for"*)
        printf "%s\n" "$(ylw "○") scanning — device off / asleep / out of range"
        ;;
      *)
        printf "%s\n" "$(ylw "?") $last_ble"
        ;;
    esac
  fi
fi

if [ "$DO_SCAN" = "1" ]; then
  printf "5. BLE scan from this shell (6s): "
  if [ ! -x "$VENV_PY" ]; then
    printf "%s\n" "$(ylw "skipped") venv missing at $VENV_PY"
  else
    ble_out=$("$VENV_PY" - <<'PYEOF' 2>&1 || true
import asyncio, sys
try:
    from bleak import BleakScanner
except ImportError:
    print("no-bleak"); sys.exit(0)
async def main():
    devs = await BleakScanner.discover(timeout=6.0)
    seen = [d for d in devs if (d.name or "").startswith("Claude-")]
    if not seen:
        print("none"); return
    for d in seen:
        print(f"{d.name}|{d.address}")
asyncio.run(main())
PYEOF
)
    case "$ble_out" in
      none)
        printf "%s\n" "$(ylw "○") no Claude-* advertising"
        ;;
      no-bleak)
        printf "%s\n" "$(ylw "skipped") bleak not installed in venv"
        ;;
      *Abort*|*SIGABRT*|*"privacy-sensitive"*|*"NSBluetoothAlwaysUsageDescription"*)
        printf "%s\n" "$(red "✗") TCC blocked — this terminal lacks NSBluetoothAlwaysUsageDescription"
        printf "      run buddy/status without --scan instead (bridge log is canonical)\n"
        ;;
      *)
        while IFS='|' read -r nm addr; do
          [ -z "$nm" ] && continue
          printf "%s\n   %s @ %s\n" "$(grn "✓")" "$nm" "$addr"
        done <<<"$ble_out"
        ;;
    esac
  fi
fi

echo
if [ "$fail" = "0" ]; then
  printf "%s\n" "$(grn "OK") — bridge reachable; if S3 still shows 'No bridge', check that the device is on and within BLE range"
  exit 0
else
  printf "%s\n" "$(red "FAIL") — bridge link broken; start with:"
  printf "   launchctl bootstrap gui/$UID ~/Library/LaunchAgents/com.kunwei.claude-buddy-bridge.plist  (or)\n"
  printf "   cd %s && .venv-session-bridge/bin/python tools/session_bridge.py --transport ble\n" "$PROJECT_ROOT"
  exit 1
fi
