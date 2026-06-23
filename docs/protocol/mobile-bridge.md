# Mobile Bridge Protocol

LAN WebSocket transport for the Expo mobile app. Hooks continue to use HTTP on port `9876`; the phone connects over WebSocket on port `9877`.

## Ports

| Port | Protocol | Consumer | Direction |
| --- | --- | --- | --- |
| `9876` | HTTP POST | `hooks/*` | Hook → bridge |
| `9877` | WebSocket | `app/` | Bridge ↔ phone |

## Wire format

All WebSocket messages are UTF-8 JSON, one object per message.

## Bridge → App

| `type` | Purpose |
| --- | --- |
| `hello` | Handshake on connect |
| `snapshot` | Heartbeat + session console fields |
| `event` | Short-lived overlay (also embedded in `snapshot.event`) |
| `pong` | Reply to app `ping` |

### `hello`

```json
{"type":"hello","bridge_version":"0.1.0","token_required":false}
```

When `token_required` is `true`, the app must send `{"cmd":"auth","token":"..."}` before other commands.

### `snapshot`

Wraps the same heartbeat fields as hardware BLE/serial (`REFERENCE.md`) plus session-console extensions:

```json
{
  "type": "snapshot",
  "total": 1,
  "running": 0,
  "waiting": 1,
  "msg": "Bash",
  "entries": [],
  "tokens": 0,
  "tokens_today": 0,
  "focused": "s_abc",
  "project": "repo",
  "branch": "main",
  "dirty": 0,
  "model": "codex",
  "assistant_msg": "editing",
  "sessions": [],
  "pending": [],
  "prompt": {},
  "event": {}
}
```

Push policy:

- Push `snapshot` immediately on state change.
- Push every 10s when unchanged (matches desktop keepalive).
- App treats the connection as dead after 30s without a downstream frame.

## App → Bridge

Reuse firmware intent commands (no new semantics):

| Command | Example |
| --- | --- |
| `permission` | `{"cmd":"permission","id":"req_123","decision":"once"}` |
| `permission` (deny) | `{"cmd":"permission","id":"req_123","decision":"deny"}` |
| `answer` (single) | `{"cmd":"answer","id":"q_transport","choice":"usb"}` |
| `answer` (multi) | `{"cmd":"answer","id":"q_multi","choices":["a","b"]}` |
| `focus` | `{"cmd":"focus","sid":"s_abc"}` |
| `event_dismiss` | `{"cmd":"event_dismiss"}` |
| `ping` | `{"type":"ping","ts":1234567890}` |

Optional auth when `token_required` is true:

```json
{"cmd":"auth","token":"..."}
```

Successful intents are written to `state.decisions` via the same path as BLE/serial `handle_device_command()`.

## LAN discovery (mDNS)

```text
_service: _buddy._tcp.local
port:     9877
txt:      version=1, http=9876, name=<hostname>
```

App flow:

1. Scan with `react-native-zeroconf`.
2. User picks a bridge or enters IP manually (fallback).
3. Connect `ws://<ip>:9877`, receive `hello`, consume snapshots.
4. MVP security: same LAN + optional pairing token printed at bridge start.

## Error handling

| Scenario | Bridge | App |
| --- | --- | --- |
| WS disconnect | Keep accepting hooks; decisions expire on timeout | Backoff reconnect; banner |
| No app during hook wait | `await_pending_decision` timeout → `{}` | — |
| mDNS failure | — | Manual IP entry |
| Concurrent approvals | First decision wins | Later submit → toast |
| Bridge restart | In-memory state lost; hooks repopulate | Reconnect, new snapshot |

## Start command

```bash
python -m bridge --transport websocket --http-port 9876 --ws-port 9877
```

Multiple transports may run in parallel; all broadcast the same snapshot. Multiple phone clients may connect; first decision wins (same as hardware).
