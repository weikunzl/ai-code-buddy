# Mobile Buddy Design

Date: 2026-06-17

Status: Accepted for implementation planning

Related ADRs:

- `docs/adr/0002-host-bridge-owns-session-state.md`
- `docs/adr/0003-backward-compatible-session-protocol.md`

## Goal

Extend claude-buddy so a phone replaces the hardware stick as the sole buddy
display and interaction surface. The desktop keeps running hooks and a local
bridge; the mobile app connects over LAN WebSocket, shows pet state, session
console, and approval UI. User-uploaded GIFs (not firmware character packs)
personalize the pet.

## Decisions Summary

| Dimension | Choice |
| --- | --- |
| Phone role | Replace hardware entirely |
| Connection | LAN only (mDNS + optional manual IP) |
| App stack | React Native / Expo |
| AI tools | Cursor + Claude Code + extensible hook adapters |
| MVP depth | Approvals, 7 pet states, session console, sounds; custom GIF upload |
| Frontend state | Zustand + WebSocket hook (no TanStack Query / RxJS in MVP) |
| Repo layout | Runtime-layered monorepo (方案 A) |
| Pet assets | User GIF per state, stored on phone only |

## Non-Goals (MVP)

- Cloud relay, push notifications, or remote access outside LAN
- Claude Desktop BLE path (requires hardware NUS; not available to phone)
- Firmware `manifest.json` character packs or folder push over bridge
- Voice notes (`audio_*` commands)
- IMU interactions (shake dizzy, face-down nap)
- User accounts or multi-tenant cloud pairing

## Architecture

```text
┌─────────────────────────────────────────────────────────┐
│  User computer (LAN)                                    │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────────┐ │
│  │ Cursor   │  │ Claude Code  │  │ bridge/          │ │
│  │ hooks    │  │ hooks        │  │ HTTP :9876       │ │
│  └────┬─────┘  └──────┬───────┘  │ WS   :9877       │ │
│       │               │          │ BridgeState      │ │
│       └───────────────┴──────────┤ mDNS _buddy._tcp │ │
│                                  └────────┬─────────┘ │
└───────────────────────────────────────────┼───────────┘
                                            │ WebSocket
┌───────────────────────────────────────────┼───────────┐
│  Phone (Expo app/)                        │           │
│  ┌────────────┐  ┌────────────┐  ┌─────────▼─────────┐ │
│  │ pet/ GIF   │  │ screens/   │  │ bridge/wsClient │ │
│  │ renderer   │  │ approval   │  │ Zustand stores  │ │
│  └────────────┘  └────────────┘  └─────────────────┘ │
│  User GIF files → app sandbox (not on bridge)          │
└────────────────────────────────────────────────────────┘

firmware/ — reference ESP32 implementation (optional, unchanged role)
```

Responsibility split (extends ADR-0002):

| Component | Owns | Does not own |
| --- | --- | --- |
| `bridge/` | Session state, pending queue, hook responses, heartbeat | Pet GIFs, UI |
| `hooks/` | AI tool event → bridge protocol translation | Session state, UI |
| `app/` | Rendering, gestures, user GIFs, local prefs | Hook internals |
| `firmware/` | Hardware reference | Mobile mainline |

## Repository Layout

```text
claude-buddy/
├── packages/
│   └── protocol/              # JSON Schema + TS types + Python models
├── bridge/
│   ├── core/                  # state, snapshot, hook ingestion
│   ├── transports/            # websocket, ble, serial
│   ├── server/                # http, discovery (mDNS)
│   └── __main__.py
├── hooks/
│   ├── common/                # relay, HTTP client
│   ├── cursor/                # hook + install
│   └── claude-code/           # hook + install
├── app/                       # Expo React Native
├── firmware/                  # migrated from root src/ + platformio.ini
├── docs/
│   ├── REFERENCE.md           # hardware BLE (unchanged)
│   └── protocol/mobile-bridge.md
└── tools/                     # dev/test scripts, install-desktop.sh
```

Dependency rules:

- `packages/protocol` is the single source of truth for wire formats.
- `hooks/*` → `bridge/server/http` only (POST).
- `app/` ↔ `bridge/transports/websocket` (bidirectional WS).
- `firmware/` and `app/` share only pet state enum names, not assets or code.

## Protocol

### Dual-channel bridge

| Port | Protocol | Consumer | Direction |
| --- | --- | --- | --- |
| `:9876` | HTTP POST | `hooks/*` | Hook → bridge |
| `:9877` | WebSocket | `app/` | Bridge ↔ phone |

Hook HTTP behavior stays compatible with existing `session_bridge.py`.
The phone is a new transport alongside BLE and USB serial, sharing
`BridgeState`.

### WebSocket frames

All messages are UTF-8 JSON, one object per message.

**Bridge → App**

| `type` | Purpose |
| --- | --- |
| `hello` | Handshake: `{type, bridge_version, token_required}` |
| `snapshot` | Heartbeat (REFERENCE.md fields + session-console extensions) |
| `event` | Short-lived overlay: `{type, event: {kind, title, text, ttl_ms}}` |
| `pong` | Heartbeat reply |

Push policy:

- Push `snapshot` immediately on state change.
- Push every 10s when unchanged (matches Claude Desktop keepalive).
- App treats connection as dead after 30s without a downstream frame.

**App → Bridge**

Reuse firmware intent commands (no new semantics):

```json
{"cmd":"permission","id":"req_123","decision":"once"}
{"cmd":"permission","id":"req_123","decision":"deny"}
{"cmd":"answer","id":"q_transport","choice":"usb"}
{"cmd":"answer","id":"q_multi","choices":["a","b"]}
{"cmd":"focus","sid":"s_abc"}
{"cmd":"event_dismiss"}
{"type":"ping","ts":1234567890}
```

Optional auth on connect when `token_required` is true:

```json
{"cmd":"auth","token":"..."}
```

Bridge writes intents into `state.decisions` via the same path as
BLE/serial `handle_device_intent()`.

### LAN discovery

mDNS service:

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

## Mobile App

### Navigation

Bottom tabs: **Pet** (home), **Sessions**, **Settings**.

`ApprovalModal` is a full-screen overlay when `pending[0]` requires user
action (not a tab).

### State management (Zustand, no Query/RxJS in MVP)

```text
wsClient.ts → snapshotStore, connectionStore
snapshotStore → derivePetState() → GifRenderer
petProfileStore (persist) → per-state user GIF URIs
ApprovalModal → wsClient.sendIntent()
```

### Pet state derivation

| Condition | State |
| --- | --- |
| Disconnected | `sleep` |
| `pending[0]` permission or `waiting > 0` | `attention` |
| `running > 0` | `busy` |
| Approve within 5s | `heart` |
| `event.kind == complete` | `celebrate` |
| Default | `idle` |

`dizzy` is not triggerable on phone in MVP (no IMU); editor may still
allow mapping a GIF for future use.

### User GIF profile

Stored locally on phone only. Not sent over bridge.

```json
{
  "version": 1,
  "name": "我的猫",
  "states": {
    "sleep": "file:///.../sleep.gif",
    "idle": "file:///.../idle.gif",
    "busy": null,
    "attention": "file:///.../alert.gif"
  },
  "fallback": "builtin_default"
}
```

Rules:

- Picker: `expo-image-picker`, GIF only.
- Copy to `FileSystem.documentDirectory/pets/<profileId>/<state>.gif`.
- Max 5MB per file.
- `null` or missing state → bundled default GIF.
- Corrupt file → fallback + toast.

Does not import firmware `manifest.json` or `characters/` packs.

### Approval UI

| `pending.kind` | UI | Outbound |
| --- | --- | --- |
| `permission` | Approve / Deny buttons | `permission` cmd |
| `single_choice` | Option list | `answer` with `choice` |
| `multi_choice` | Multi-select + confirm | `answer` with `choices` |
| `free_text_required` (with options) | Quick replies | `answer` with `choice` |
| `notice` | Snackbar only | no answer |
| `free_text_required` (no options) | Info card | no answer |

Hook adapters fail open on timeout (25–30s); app shows timeout message.

### Sounds

Built-in assets under `app/assets/sounds/`, roles aligned with firmware:
`input_required`, `answer_sent`, `deny`, `complete`, `ui_click`. Play via
`expo-av`; global mute in settings.

### Reconnection

Exponential backoff: 1s → 2s → 4s → 8s → max 30s. Retry immediately when
app returns to foreground. States: `disconnected → discovering →
connecting → connected`.

### Core dependencies

- `expo`, `zustand`, `react-native-zeroconf`, `@react-navigation/native`
- `expo-image-picker`, `expo-file-system`, `expo-av`

## Bridge Refactor

Extract from `tools/session_bridge.py`:

| Current | Target |
| --- | --- |
| `BridgeState`, models | `bridge/core/state.py` |
| `build_heartbeat`, `apply_hook` | `bridge/core/snapshot.py`, `hooks.py` |
| HTTP server | `bridge/server/http.py` |
| BLE/Serial transports | `bridge/transports/ble.py`, `serial.py` |
| Device intent handling | `bridge/transports/base.py` |
| New | `bridge/transports/websocket.py` |
| New | `bridge/server/discovery.py` |

Start command:

```bash
python -m bridge --transport websocket --ws-port 9877 --http-port 9876
```

Multiple transports may run in parallel; all broadcast the same snapshot.
Multiple phone clients may connect; first decision wins (same as hardware).

Keep `tools/session_bridge.py` as a thin wrapper during migration.

## Hooks

```
hooks/common/relay.py     stdin JSON → POST bridge
hooks/common/client.py    BUDDY_BRIDGE_URL (compat CURSOR_BUDDY_BRIDGE_URL)
hooks/cursor/hook.py      from tools/cursor_hook.py
hooks/cursor/install.py   ~/.cursor/hooks.json
hooks/claude-code/hook.py SessionStart, UserPromptSubmit, Stop, PreToolUse, Notification
hooks/claude-code/install.py
```

Adapter interface:

```python
class HookAdapter(Protocol):
    def translate(self, stdin_json: dict) -> dict: ...
    def respond(self, bridge_response: dict) -> dict: ...
```

Desktop install:

```bash
./tools/install-desktop.sh
# pip install -e bridge/
# python -m hooks.cursor.install
# python -m hooks.claude-code.install
# register LaunchAgent (macOS) or print manual start instructions
```

## Migration Plan

| Phase | Work | Verification |
| --- | --- | --- |
| M1 | `git mv` firmware to `firmware/`; update CI paths | `cd firmware && pio run` |
| M2 | Extract `packages/protocol` and `bridge/`; wrapper for old entrypoint | existing `tools/test_*.py` |
| M3 | Move hooks; add WS transport + mDNS | `test_bridge_ws.py` |
| M4 | Scaffold `app/`; end-to-end LAN approval | manual + app unit tests |

Each phase is an independently mergeable PR.

## Error Handling

| Scenario | Bridge | App |
| --- | --- | --- |
| WS disconnect | Keep accepting hooks; decisions expire on timeout | Backoff reconnect; banner |
| No app during hook wait | `await_pending_decision` timeout → `{}` | — |
| mDNS failure | — | Manual IP entry |
| Corrupt user GIF | — | Default GIF + toast |
| Concurrent approvals | First decision wins | Later submit → toast |
| Bridge restart | In-memory state lost; hooks repopulate | Reconnect, new snapshot |

## Testing

**Bridge (Python)**

- `tools/test_bridge_http.py` — hook POST → state
- `tools/test_bridge_ws.py` — WS push + intent loop
- `tools/test_bridge_discovery.py` — mDNS (mocked)
- Migrate `tools/test_cursor_hook.py`, add `test_claude_code_hook.py`

**App (Jest)**

- Unit: `derivePetState`, frame parser, pet profile persistence
- Integration: mock WS → store → ApprovalModal
- Manual: real device on same WiFi, Cursor risky command approval

**Firmware**

- Unchanged: `cd firmware && pio run` after M1 move

## Legacy Mapping

| Current path | Target |
| --- | --- |
| `src/` | `firmware/src/` |
| `platformio.ini` | `firmware/platformio.ini` |
| `characters/` | `firmware/characters/` |
| `tools/session_bridge.py` | `bridge/` (+ thin wrapper) |
| `tools/cursor_hook.py` | `hooks/cursor/hook.py` |
| `tools/cursor_buddy_install.py` | `hooks/cursor/install.py` |
| `tools/hook_relay.py` | `hooks/common/relay.py` |

## Documentation Deliverables

- This spec
- `docs/protocol/mobile-bridge.md` — WS protocol detail (during M3)
- Root README section for mobile + desktop setup (during M4)
