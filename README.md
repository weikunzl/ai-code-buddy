# DevPet (claude-buddy)

**[中文版 README](README.zh-CN.md)**

A phone-based desk pet for AI coding sessions. Your companion wakes when work
starts, gets alert when a permission is waiting, and lets you **approve or deny
risky commands from your phone** instead of alt-tabbing back to the IDE.

DevPet is the **Expo mobile app** in [`app/`](app/). Your computer runs a
local **bridge** and lightweight **hooks** for Cursor and Claude Code on the
same Wi‑Fi. Session snapshots and pet states reuse the wire format from the
original ESP32 buddy firmware — see [Firmware reference](#firmware-reference)
(optional, for hardware makers only).

> Design spec: [`docs/superpowers/specs/2026-06-17-mobile-buddy-design.md`](docs/superpowers/specs/2026-06-17-mobile-buddy-design.md)

## DevPet — mobile features

| Area | What you get |
| --- | --- |
| **Home** | Animated pet (7 states), session banner, stats, one-tap reconnect |
| **Approvals** | Global modal on any tab — allow once / deny shell commands and choices |
| **Sessions** | List active and recent sessions, tap to **focus**, pending queue, activity feed |
| **Pet GIFs** | Pick your own GIF per state from the photo library (≤ 5 MB) |
| **Sounds** | In-app approval cues (`expo-audio`), mute in Settings |
| **Notifications** | Lock-screen alerts on iOS / dev builds; Expo Go on Android uses in-app sounds only |
| **Settings** | LAN IP + port, companion name, language, sounds |
| **Bridge guide** | First-launch setup walkthrough + link to full install steps |
| **Help** | Collapsible FAQ at the bottom of Settings (connection, ports, hooks, sessions) |
| **i18n** | English, 中文, 한국어, Русский |

### Pet states

| State | When |
| --- | --- |
| `sleep` | Bridge not connected |
| `idle` | Connected, nothing urgent |
| `busy` | Sessions running |
| `attention` | Approval or choice pending |
| `celebrate` | Session finished |
| `heart` | You approved in under 5 seconds |
| `dizzy` | Reserved (hardware IMU only in firmware) |

### Custom GIFs

In **Settings → Customize GIFs**, assign one GIF per state or use built-in
placeholders. Files stay on the phone; the bridge never receives your assets.

## How it works

```text
┌──────────────── Computer (same Wi‑Fi) ─────────────────┐
│  Cursor / Claude Code  →  hooks/  →  bridge/         │
│                          HTTP :9876    WS :9877        │
└────────────────────────────┬───────────────────────────┘
                             │ WebSocket snapshots
                             ▼
┌──────────────── Phone — DevPet (Expo) ─────────────────┐
│  Pet · Sessions · Approvals · Settings · Help        │
└──────────────────────────────────────────────────────┘
```

| Piece | Role |
| --- | --- |
| **App** | UI, pet, GIFs, notifications, local preferences |
| **Bridge** | Session state, pending decisions, heartbeat to phone |
| **Hooks** | Cursor / Claude Code events → bridge protocol |

Protocol shapes (heartbeat, `permission`, `answer`, `focus`) follow the
[ESP32 firmware reference](firmware/README.md); the phone uses **LAN
WebSocket**, not BLE.

## Installation

Phone + computer on the **same Wi‑Fi**. Full steps:

### Prerequisites

| Requirement | Notes |
| --- | --- |
| Python 3.10+ | Bridge and hooks |
| Node.js 18+ | Optional — `devpet-bridge` global CLI |
| Git | Clone repo for hook install (required) |
| Cursor or Claude Code | Hook integration |
| Phone | [Expo Go](https://expo.dev/go) or dev build |

| Port | Protocol | Consumer |
| --- | --- | --- |
| `9876` | HTTP POST | `hooks/*` |
| `9877` | WebSocket | `app/` |

### 1. Clone & desktop setup

```bash
git clone https://github.com/weikunzl/ai-code-buddy.git
cd ai-code-buddy
./tools/install-desktop.sh    # pip install bridge + Cursor/Claude hooks
```

Use a venv if you prefer: `python3 -m venv .venv && source .venv/bin/activate`

### 2. Bridge CLI (optional)

```bash
npm install -g github:weikunzl/ai-code-buddy#feat/mobile-buddy
devpet-bridge restart    # kill stale listeners, start HTTP+WS
```

Hooks still need a **git clone** (Step 1). CLI only starts the bridge.

### 3. Start bridge

```bash
devpet-bridge restart
# or: ./tools/restart_bridge.sh
```

Hooks **auto-start** the bridge when idle (`BUDDY_BRIDGE_AUTOSTART=1`, default).

### 4. Phone app

```bash
cd app && npm install && npm start
```

1. Scan QR with Expo Go (same Wi‑Fi as the computer).
2. First launch opens the **Bridge setup guide** (also in Settings).
3. Enter computer **LAN IP** → `ws://<ip>:9877` → **Connect**.

### 5. Verify

```bash
python3 tools/push_test_prompt.py   # approval should appear on phone
cd app && npm test
```

**Troubleshooting:** WebSocket errors → correct LAN IP (not `127.0.0.1`), same
Wi‑Fi, `devpet-bridge restart`. Expand **Help** in Settings for more.

### Quick reference

```bash
./tools/install-desktop.sh
npm install -g github:weikunzl/ai-code-buddy#feat/mobile-buddy
devpet-bridge restart
cd app && npm start
```

## Cursor integration

[`hooks/cursor/hook.py`](hooks/cursor/hook.py) maps [Cursor agent hooks](https://cursor.com/docs/hooks) to bridge events. Install:

```bash
python3 hooks/cursor/install.py
```

| `CURSOR_BUDDY_APPROVE` | Behavior |
| --- | --- |
| `risky` (default) | Block destructive / network shell commands for phone approval |
| `all` | Every shell command waits |
| `off` | Observe only |

Timeout default 25s — fails open to Cursor's normal prompt. See
[`hooks/cursor/install.py`](hooks/cursor/install.py) for uninstall.

## Project layout

```text
claude-buddy/
├── app/                   # DevPet — Expo mobile app (main product)
├── bridge/                # Python daemon: HTTP, WebSocket, mDNS
├── hooks/                 # Cursor + Claude Code adapters
├── packages/protocol/     # Shared JSON / TS / Python types
├── firmware/              # ESP32 reference (optional) → firmware/README.md
├── docs/                  # Design specs + mobile protocol
├── package.json           # devpet-cli (`devpet-bridge`)
└── tools/                 # Installers, smoke tests
```

## Protocol

| Document | Audience |
| --- | --- |
| [`docs/protocol/mobile-bridge.md`](docs/protocol/mobile-bridge.md) | WebSocket frames |
| [`docs/superpowers/specs/2026-06-17-mobile-buddy-design.md`](docs/superpowers/specs/2026-06-17-mobile-buddy-design.md) | Architecture |
| [`firmware/README.md`](firmware/README.md) | BLE hardware (reference) |
| [`REFERENCE.md`](REFERENCE.md) | BLE wire protocol |

Completed sessions stay visible **24 hours**; `total` counts only active
(`running` / `waiting`) sessions.

## Development

```bash
devpet-bridge restart
python3 tools/test_bridge_http.py
python3 tools/test_cursor_hook.py
cd app && npm test
```

See [`AGENTS.md`](AGENTS.md) and [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Firmware reference

The repo includes an **optional** ESP32 desk-pet implementation under
[`firmware/`](firmware/) (M5StickC / StickS3, BLE + Claude Desktop). DevPet's
bridge and app were built **on top of that protocol** — same pet states and
device intents — but phone users only need `app/` + bridge + hooks.

→ **[firmware/README.md](firmware/README.md)** for build, flash, and BLE docs.

## Roadmap

| Phase | Status |
| --- | --- |
| M1–M4 | Done — mobile app, bridge, hooks, WebSocket |
| Next | mDNS auto-pair, dev build notifications, optional phone `preToolUse` |

## Sponsorship

If DevPet saves you context switches, consider buying me a coffee ☕️

| Alipay | WeChat |
| --- | --- |
| <img src="docs/sponsor/alipay.png" alt="Alipay" width="220"> | <img src="docs/sponsor/wechat.png" alt="WeChat" width="220"> |

[GitHub Sponsors](https://github.com/sponsors/weikunzl) (setup in progress).

## Availability

Hook + bridge + phone is a **local, opt-in developer tool** (LAN only in the
MVP design). BLE Hardware Buddy in Claude Desktop remains a separate maker
surface — see [`firmware/README.md`](firmware/README.md).
