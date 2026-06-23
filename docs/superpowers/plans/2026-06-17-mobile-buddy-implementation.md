# Mobile Buddy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a mobile-first claude-buddy monorepo where an Expo phone app replaces the hardware stick, connecting over LAN WebSocket to a refactored Python bridge fed by Cursor and Claude Code hooks.

**Architecture:** Migrate firmware to `firmware/`, extract `tools/session_bridge.py` into `bridge/` with HTTP (`:9876`) and WebSocket (`:9877`) transports, move hooks into `hooks/`, share wire types via `packages/protocol`, and build `app/` with Zustand + a WebSocket client. Bridge owns session state (ADR-0002); app owns pet GIFs locally.

**Tech Stack:** Python 3.11+ (`bridge/`, `hooks/`), PlatformIO/Arduino (`firmware/`), Expo SDK 52 / React Native / TypeScript / Zustand (`app/`), `websockets`, `zeroconf`, Jest, existing `unittest` smoke tests under `tools/`.

**Spec:** [`docs/superpowers/specs/2026-06-17-mobile-buddy-design.md`](../specs/2026-06-17-mobile-buddy-design.md)

**Recommended execution:** One milestone per PR / branch. Run in a git worktree (`superpowers:using-git-worktrees`) before M2.

---

## File Structure (target)

```text
packages/protocol/
  schemas/snapshot.json
  schemas/intent.json
  ts/index.ts
  python/models.py
bridge/
  pyproject.toml
  core/state.py
  core/snapshot.py
  core/hooks.py
  core/intent.py
  transports/base.py
  transports/websocket.py
  transports/ble.py
  transports/serial.py
  server/http.py
  server/discovery.py
  __main__.py
hooks/
  common/client.py
  common/relay.py
  cursor/hook.py
  cursor/install.py
  claude-code/hook.py
  claude-code/install.py
app/
  package.json
  src/bridge/wsClient.ts
  src/bridge/discovery.ts
  src/store/snapshot.ts
  src/store/connection.ts
  src/store/petProfile.ts
  src/pet/derivePetState.ts
  src/pet/GifRenderer.tsx
  src/screens/HomeScreen.tsx
  src/screens/SessionsScreen.tsx
  src/screens/SettingsScreen.tsx
  src/screens/PetEditorScreen.tsx
  src/components/ApprovalModal.tsx
  src/navigation/RootNavigator.tsx
firmware/               # git mv from repo root
  platformio.ini
  src/
  characters/
tools/
  session_bridge.py       # thin wrapper → python -m bridge
  test_bridge_http.py
  test_bridge_ws.py
  test_bridge_discovery.py
  install-desktop.sh
docs/protocol/mobile-bridge.md
```

---

## Milestone M1 — Firmware relocation

### Task M1-1: Move PlatformIO tree into `firmware/`

**Files:**
- Move: `src/` → `firmware/src/`
- Move: `platformio.ini` → `firmware/platformio.ini`
- Move: `partitions_8mb.csv` → `firmware/partitions_8mb.csv`
- Move: `characters/` → `firmware/characters/`
- Modify: `firmware/platformio.ini` (paths if needed)
- Modify: `AGENTS.md`
- Modify: `README.md` (remove “today vs target” note for firmware paths)

- [ ] **Step 1: Move files with git history**

```bash
cd /path/to/claude-buddy
git mv src firmware/src
git mv platformio.ini firmware/platformio.ini
git mv partitions_8mb.csv firmware/partitions_8mb.csv
git mv characters firmware/characters
```

- [ ] **Step 2: Verify firmware build**

```bash
cd firmware && pio run -e m5sticks3
```

Expected: `SUCCESS` (same as pre-move baseline).

- [ ] **Step 3: Update `AGENTS.md` build commands**

Replace root `pio run` examples with:

```markdown
- `cd firmware && pio run` builds the default PlatformIO environment.
- `cd firmware && pio run -e m5stickc-plus` builds for the original M5StickC Plus.
- `cd firmware && pio run -e m5sticks3` builds for M5 StickS3.
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor: move firmware tree under firmware/"
```

---

## Milestone M2 — Protocol package + bridge extraction

### Task M2-1: Scaffold `packages/protocol`

**Files:**
- Create: `packages/protocol/schemas/snapshot.json`
- Create: `packages/protocol/schemas/intent.json`
- Create: `packages/protocol/ts/index.ts`
- Create: `packages/protocol/python/models.py`
- Create: `packages/protocol/python/__init__.py`

- [ ] **Step 1: Add snapshot schema**

Create `packages/protocol/schemas/snapshot.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "BuddySnapshot",
  "type": "object",
  "required": ["type", "total", "running", "waiting"],
  "properties": {
    "type": { "const": "snapshot" },
    "total": { "type": "integer", "minimum": 0 },
    "running": { "type": "integer", "minimum": 0 },
    "waiting": { "type": "integer", "minimum": 0 },
    "msg": { "type": "string" },
    "entries": { "type": "array", "items": { "type": "string" } },
    "tokens": { "type": "integer" },
    "tokens_today": { "type": "integer" },
    "focused": { "type": "string" },
    "project": { "type": "string" },
    "branch": { "type": "string" },
    "dirty": { "type": "integer" },
    "model": { "type": "string" },
    "assistant_msg": { "type": "string" },
    "sessions": { "type": "array" },
    "pending": { "type": "array" },
    "prompt": { "type": "object" },
    "event": { "type": "object" }
  },
  "additionalProperties": true
}
```

- [ ] **Step 2: Add TypeScript types**

Create `packages/protocol/ts/index.ts`:

```typescript
export type PetState =
  | "sleep"
  | "idle"
  | "busy"
  | "attention"
  | "celebrate"
  | "dizzy"
  | "heart";

export type PendingKind =
  | "permission"
  | "single_choice"
  | "multi_choice"
  | "notice"
  | "free_text_required";

export interface PendingItem {
  id: string;
  sid: string;
  kind: PendingKind;
  title: string;
  body: string;
  options?: Array<{ id: string; label: string; desc?: string }>;
}

export interface BuddySnapshot {
  type: "snapshot";
  total: number;
  running: number;
  waiting: number;
  msg?: string;
  entries?: string[];
  tokens?: number;
  tokens_today?: number;
  focused?: string;
  project?: string;
  branch?: string;
  dirty?: number;
  model?: string;
  assistant_msg?: string;
  sessions?: Array<Record<string, unknown>>;
  pending?: PendingItem[];
  prompt?: { id: string; tool?: string; hint?: string };
  event?: { kind: string; title?: string; text?: string; ttl_ms?: number };
}

export interface PermissionIntent {
  cmd: "permission";
  id: string;
  decision: "once" | "deny";
}

export interface AnswerIntent {
  cmd: "answer";
  id: string;
  choice?: string;
  choices?: string[];
}

export type DeviceIntent = PermissionIntent | AnswerIntent | { cmd: string; [key: string]: unknown };
```

- [ ] **Step 3: Commit**

```bash
git add packages/protocol
git commit -m "feat: add shared protocol schemas and TS types"
```

### Task M2-2: Extract `bridge/core/state.py` with tests

**Files:**
- Create: `bridge/pyproject.toml`
- Create: `bridge/core/__init__.py`
- Create: `bridge/core/state.py`
- Create: `tools/test_bridge_http.py` (initial tests import bridge package)
- Modify: `tools/test_session_bridge.py` (keep passing via wrapper until cutover)

- [ ] **Step 1: Write failing state tests**

Create `tools/test_bridge_http.py`:

```python
#!/usr/bin/env python3
import unittest

from bridge.core.state import BridgeState


class BridgeStateTests(unittest.TestCase):
    def test_build_heartbeat_includes_session_console_fields(self):
        state = BridgeState()
        state.upsert_session(
            sid="s_123",
            cwd="/tmp/repo",
            project="repo",
            branch="main",
            dirty=1,
            phase="running",
            model="codex",
            last="editing",
            now=1000,
        )
        hb = state.build_heartbeat(now=1540)
        self.assertEqual(hb["total"], 1)
        self.assertEqual(hb["running"], 1)
        self.assertEqual(hb["project"], "repo")
        self.assertEqual(hb["sessions"][0]["sid"], "s_123")

    def test_permission_decision_via_handle_device_command(self):
        state = BridgeState()
        state.upsert_session(
            sid="s_1", cwd="/tmp", project="p", branch="main", dirty=0,
            phase="waiting", model="codex", last="x", now=10,
        )
        state.add_pending("req_1", "s_1", "permission", "Bash", "rm -rf /tmp/x", [], now=10)
        ok = state.handle_device_command({"cmd": "permission", "id": "req_1", "decision": "once"})
        self.assertTrue(ok)
        self.assertEqual(state.decisions["req_1"], "once")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
PYTHONPATH=. python3 tools/test_bridge_http.py
```

Expected: `ModuleNotFoundError: No module named 'bridge'`

- [ ] **Step 3: Create package scaffold**

Create `bridge/pyproject.toml`:

```toml
[project]
name = "claude-buddy-bridge"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = []

[tool.setuptools.packages.find]
where = ["."]
```

- [ ] **Step 4: Move `BridgeState` and models from `tools/session_bridge.py`**

Cut `Session`, `Pending`, `AudioUpload`, `BridgeState` (lines ~60–465) into `bridge/core/state.py`. Keep imports (`dataclasses`, `threading`, `time`, `collections`, `typing`, `base64`, `json`, `os`, `wave`, `pathlib` as used).

Add at top of `bridge/core/state.py`:

```python
from bridge.core.state import BridgeState  # noqa — public API
```

Export `BridgeState` from `bridge/core/__init__.py`:

```python
from bridge.core.state import BridgeState, Session, Pending

__all__ = ["BridgeState", "Session", "Pending"]
```

- [ ] **Step 5: Run test — expect PASS**

```bash
PYTHONPATH=. python3 tools/test_bridge_http.py
```

- [ ] **Step 6: Commit**

```bash
git add bridge tools/test_bridge_http.py
git commit -m "feat: extract BridgeState into bridge package"
```

### Task M2-3: Extract hook ingestion + HTTP server

**Files:**
- Create: `bridge/core/hooks.py`
- Create: `bridge/core/snapshot.py` (simulator helpers if needed)
- Create: `bridge/server/http.py`
- Create: `bridge/__main__.py` (partial — HTTP only first)
- Modify: `tools/session_bridge.py` → thin re-export wrapper

- [ ] **Step 1: Move `apply_hook`, `await_pending_decision`, `notification_prompt`, git helpers into `bridge/core/hooks.py`**

`apply_hook` signature stays:

```python
def apply_hook(
    state: BridgeState,
    payload: dict[str, Any],
    now: int | None = None,
    wait_for_decision: bool = True,
    decision_timeout: float = 30.0,
    on_state_change: Any = None,
) -> dict[str, Any]:
    ...
```

- [ ] **Step 2: Move `run_http` into `bridge/server/http.py`**

```python
def run_http(state: BridgeState, runtime: "BridgeRuntime", port: int, host: str = "127.0.0.1") -> HTTPServer:
    ...
```

- [ ] **Step 3: Add HTTP integration test**

Append to `tools/test_bridge_http.py`:

```python
import json
import threading
import urllib.request

from bridge.core.hooks import apply_hook
from bridge.core.state import BridgeState
from bridge.server.http import run_http


class HttpServerTests(unittest.TestCase):
    def test_post_notification_single_choice(self):
        state = BridgeState()
        runtime = _FakeRuntime(state)
        server = run_http(state, runtime, port=19876)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        payload = {
            "hook_event_name": "Notification",
            "session_id": "s_demo",
            "cwd": "/tmp",
            "message": "Choose",
            "prompt": {
                "id": "q1",
                "kind": "single_choice",
                "title": "Pick",
                "body": "one",
                "options": [{"id": "a", "label": "A"}],
            },
        }
        # Pre-resolve decision so POST does not block 30s
        def decide():
            import time
            time.sleep(0.1)
            state.handle_device_command({"cmd": "answer", "id": "q1", "choice": "a"})
        threading.Thread(target=decide, daemon=True).start()
        req = urllib.request.Request(
            "http://127.0.0.1:19876",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read().decode())
        self.assertEqual(body, {"decision": "a"})
        server.shutdown()


class _FakeRuntime:
    def __init__(self, state: BridgeState) -> None:
        self.state = state
        self.bump = threading.Event()
```

- [ ] **Step 4: Run tests**

```bash
PYTHONPATH=. python3 tools/test_bridge_http.py
```

Expected: all PASS.

- [ ] **Step 5: Replace `tools/session_bridge.py` body with wrapper**

```python
#!/usr/bin/env python3
"""Backward-compatible entrypoint. Prefer: python -m bridge"""
from bridge.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
```

Move remaining runtime (`BridgeRuntime`, transports, `main`) into `bridge/__main__.py` incrementally; until then wrapper can import legacy implementations.

- [ ] **Step 6: Ensure existing tests still pass**

```bash
PYTHONPATH=. python3 tools/test_session_bridge.py
PYTHONPATH=. python3 tools/test_cursor_hook.py
```

- [ ] **Step 7: Commit**

```bash
git add bridge tools/session_bridge.py tools/test_bridge_http.py
git commit -m "feat: extract HTTP hook server into bridge package"
```

---

## Milestone M3 — WebSocket transport, mDNS, hooks relocation

### Task M3-1: WebSocket transport

**Files:**
- Create: `bridge/transports/websocket.py`
- Create: `bridge/core/runtime.py` (`BridgeRuntime` multi-transport fan-out)
- Create: `tools/test_bridge_ws.py`
- Modify: `bridge/pyproject.toml` (add `websockets`)
- Create: `docs/protocol/mobile-bridge.md`

- [ ] **Step 1: Write failing WS test**

Create `tools/test_bridge_ws.py`:

```python
#!/usr/bin/env python3
import asyncio
import json
import threading
import unittest

import websockets

from bridge.core.state import BridgeState
from bridge.core.runtime import BridgeRuntime
from bridge.transports.websocket import WebSocketTransport


class WebSocketTransportTests(unittest.TestCase):
    def test_push_snapshot_and_receive_permission(self):
        state = BridgeState()
        state.upsert_session(
            sid="s_1", cwd="/tmp", project="p", branch="main", dirty=0,
            phase="waiting", model="codex", last="x", now=1,
        )
        state.add_pending("req_1", "s_1", "permission", "Bash", "ls", [], now=1)
        transport = WebSocketTransport(host="127.0.0.1", port=19877)
        runtime = BridgeRuntime(state, [transport])
        transport.start(runtime.on_device_message)
        runtime.send_snapshot()

        async def client_flow():
            async with websockets.connect("ws://127.0.0.1:19877") as ws:
                hello = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
                self.assertEqual(hello["type"], "hello")
                snap = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
                self.assertEqual(snap["type"], "snapshot")
                self.assertEqual(snap["waiting"], 1)
                await ws.send(json.dumps({"cmd": "permission", "id": "req_1", "decision": "once"}))
                await asyncio.sleep(0.2)
            self.assertEqual(state.decisions.get("req_1"), "once")

        asyncio.run(client_flow())
        transport.stop()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
PYTHONPATH=. python3 tools/test_bridge_ws.py
```

- [ ] **Step 3: Implement `WebSocketTransport`**

Create `bridge/transports/websocket.py` with:

- `start(on_message: Callable[[dict], None])` — asyncio loop in daemon thread
- On connect: send `{"type":"hello","bridge_version":"0.1.0","token_required":false}`
- `write(obj: dict)` — wrap snapshot as `{"type":"snapshot", **heartbeat}`
- Parse inbound JSON; call `state.handle_device_command`; invoke `runtime.bump.set()` on success
- Track multiple clients in a `set`; broadcast writes to all

Add dependency in `bridge/pyproject.toml`:

```toml
dependencies = ["websockets>=12.0"]
```

Create `bridge/core/runtime.py`:

```python
class BridgeRuntime:
    def __init__(self, state: BridgeState, transports: list[Any]) -> None:
        self.state = state
        self.transports = transports
        self.bump = threading.Event()
        self.stopped = threading.Event()

    def send_snapshot(self) -> None:
        hb = self.state.build_heartbeat()
        frame = {"type": "snapshot", **hb}
        for t in self.transports:
            t.write(frame)

    def on_device_message(self, obj: dict[str, Any]) -> None:
        if self.state.handle_device_command(obj):
            self.bump.set()
```

- [ ] **Step 4: Run test — expect PASS**

```bash
pip install -e bridge/
PYTHONPATH=. python3 tools/test_bridge_ws.py
```

- [ ] **Step 5: Document protocol**

Create `docs/protocol/mobile-bridge.md` with hello/snapshot/intent tables from design spec.

- [ ] **Step 6: Commit**

```bash
git add bridge tools/test_bridge_ws.py docs/protocol/mobile-bridge.md
git commit -m "feat: add WebSocket transport for mobile app"
```

### Task M3-2: mDNS discovery

**Files:**
- Create: `bridge/server/discovery.py`
- Create: `tools/test_bridge_discovery.py`
- Modify: `bridge/pyproject.toml` (add `zeroconf`)

- [ ] **Step 1: Write discovery test with mock**

```python
#!/usr/bin/env python3
import unittest
from unittest.mock import MagicMock, patch

from bridge.server.discovery import BuddyDiscovery


class DiscoveryTests(unittest.TestCase):
    @patch("bridge.server.discovery.Zeroconf")
    def test_register_service(self, mock_zc_cls):
        mock_zc = MagicMock()
        mock_zc_cls.return_value = mock_zc
        disc = BuddyDiscovery(ws_port=9877, http_port=9876, name="dev-mac")
        disc.register()
        mock_zc.register_service.assert_called_once()
        disc.unregister()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Implement `BuddyDiscovery`**

Service type `_buddy._tcp.local.`, properties `version=1`, `http=9876`, `name=<hostname>`.

- [ ] **Step 3: Wire into `bridge/__main__.py`**

```python
parser.add_argument("--ws-port", type=int, default=9877)
parser.add_argument("--transport", default="websocket")
# When websocket in transport list, start WebSocketTransport + BuddyDiscovery
```

- [ ] **Step 4: Commit**

```bash
git add bridge/server/discovery.py tools/test_bridge_discovery.py bridge/__main__.py
git commit -m "feat: broadcast bridge via mDNS"
```

### Task M3-3: Relocate hooks

**Files:**
- Create: `hooks/common/client.py`
- Create: `hooks/common/relay.py`
- Create: `hooks/cursor/hook.py`
- Create: `hooks/cursor/install.py`
- Create: `hooks/claude-code/hook.py`
- Create: `hooks/claude-code/install.py`
- Create: `tools/install-desktop.sh`
- Modify: `tools/cursor_hook.py` → wrapper
- Modify: `tools/hook_relay.py` → wrapper

- [ ] **Step 1: Move relay + client**

`hooks/common/client.py`:

```python
import os

def bridge_url() -> str:
    return (
        os.environ.get("BUDDY_BRIDGE_URL")
        or os.environ.get("CURSOR_BUDDY_BRIDGE_URL")
        or "http://127.0.0.1:9876"
    )
```

Move `hook_relay.py` logic to `hooks/common/relay.py` unchanged except import `bridge_url`.

- [ ] **Step 2: Move cursor hook + install**

`git mv tools/cursor_hook.py hooks/cursor/hook.py`

Update `hooks/cursor/install.py` `HOOK_SCRIPT` path:

```python
HOOK_SCRIPT = REPO_ROOT / "hooks" / "cursor" / "hook.py"
```

Leave `tools/cursor_hook.py` as:

```python
#!/usr/bin/env python3
from hooks.cursor.hook import main
if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Add Claude Code hook (relay-only MVP)**

`hooks/claude-code/hook.py` reads stdin JSON; if it already has `hook_event_name`, POST as-is via `hooks/common/relay.py`; map missing fields (`session_id`, `cwd`) from env fallbacks.

`hooks/claude-code/install.py` documents manual `settings.json` snippet (Claude Code hook paths vary by install).

- [ ] **Step 4: Add `tools/install-desktop.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
pip install -e "$ROOT/bridge"
python3 "$ROOT/hooks/cursor/install.py"
python3 "$ROOT/hooks/claude-code/install.py"
echo "Start bridge: python3 -m bridge --transport websocket --http-port 9876 --ws-port 9877"
```

- [ ] **Step 5: Run hook tests**

```bash
PYTHONPATH=. python3 tools/test_cursor_hook.py
PYTHONPATH=. python3 tools/test_hook_relay.py
```

- [ ] **Step 6: Commit**

```bash
git add hooks tools/install-desktop.sh tools/cursor_hook.py tools/hook_relay.py
git commit -m "refactor: move hooks into hooks/ package layout"
```

---

## Milestone M4 — Expo mobile app

### Task M4-1: Scaffold Expo app

**Files:**
- Create: `app/package.json`
- Create: `app/app.json`
- Create: `app/tsconfig.json`
- Create: `app/babel.config.js`
- Symlink or copy: `packages/protocol/ts` → `app/src/protocol` (or npm `file:` dep)

- [ ] **Step 1: Create Expo project**

```bash
cd app
npx create-expo-app@latest . --template blank-typescript
npm install zustand @react-navigation/native @react-navigation/bottom-tabs react-native-screens react-native-safe-area-context react-native-zeroconf expo-image-picker expo-file-system expo-av
npx expo install react-native-gesture-handler
```

- [ ] **Step 2: Add path alias in `tsconfig.json`**

```json
{
  "compilerOptions": {
    "paths": {
      "@protocol/*": ["../packages/protocol/ts/*"]
    }
  }
}
```

- [ ] **Step 3: Commit scaffold**

```bash
git add app
git commit -m "feat: scaffold Expo mobile app"
```

### Task M4-2: `derivePetState` + unit tests (TDD)

**Files:**
- Create: `app/src/pet/derivePetState.ts`
- Create: `app/src/pet/derivePetState.test.ts`
- Modify: `app/package.json` (jest config)

- [ ] **Step 1: Write failing tests**

```typescript
// app/src/pet/derivePetState.test.ts
import { derivePetState } from "./derivePetState";
import type { BuddySnapshot } from "@protocol/index";

const base: BuddySnapshot = {
  type: "snapshot",
  total: 1,
  running: 0,
  waiting: 0,
};

test("disconnected → sleep", () => {
  expect(derivePetState(null, false)).toBe("sleep");
});

test("waiting permission → attention", () => {
  const snap: BuddySnapshot = {
    ...base,
    waiting: 1,
    pending: [{ id: "p1", sid: "s1", kind: "permission", title: "Bash", body: "ls" }],
  };
  expect(derivePetState(snap, true)).toBe("attention");
});

test("running sessions → busy", () => {
  expect(derivePetState({ ...base, running: 1 }, true)).toBe("busy");
});
```

- [ ] **Step 2: Run — expect FAIL**

```bash
cd app && npm test -- derivePetState
```

- [ ] **Step 3: Implement**

```typescript
// app/src/pet/derivePetState.ts
import type { BuddySnapshot, PetState } from "@protocol/index";

export function derivePetState(
  snapshot: BuddySnapshot | null,
  connected: boolean,
  recentApproveAt?: number,
  now = Date.now(),
): PetState {
  if (!connected) return "sleep";
  if (recentApproveAt && now - recentApproveAt < 5000) return "heart";
  const pending = snapshot?.pending?.[0];
  if (snapshot?.waiting && snapshot.waiting > 0) return "attention";
  if (pending?.kind === "permission") return "attention";
  if (snapshot?.event?.kind === "complete") return "celebrate";
  if ((snapshot?.running ?? 0) > 0) return "busy";
  return "idle";
}
```

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add app/src/pet
git commit -m "feat: add pet state derivation with tests"
```

### Task M4-3: WebSocket client + Zustand stores

**Files:**
- Create: `app/src/bridge/wsClient.ts`
- Create: `app/src/bridge/frameParser.ts`
- Create: `app/src/store/snapshot.ts`
- Create: `app/src/store/connection.ts`
- Create: `app/src/bridge/wsClient.test.ts`

- [ ] **Step 1: Frame parser test**

```typescript
import { parseBridgeMessage } from "./frameParser";

test("parses snapshot", () => {
  const msg = parseBridgeMessage('{"type":"snapshot","total":0,"running":0,"waiting":0}');
  expect(msg?.type).toBe("snapshot");
});
```

- [ ] **Step 2: Implement `wsClient.ts`**

Key API:

```typescript
export type WsClientOptions = {
  url: string;
  onSnapshot: (snap: BuddySnapshot) => void;
  onHello: (hello: { token_required: boolean }) => void;
  onConnectionChange: (status: ConnectionStatus) => void;
};

export function createWsClient(opts: WsClientOptions): {
  connect: () => void;
  disconnect: () => void;
  sendIntent: (intent: DeviceIntent) => void;
};
```

Reconnect: backoff 1→2→4→8→30s max; reset on successful `hello`.

- [ ] **Step 3: Zustand stores**

`connection.ts`: `status`, `bridgeHost`, `lastFrameAt`

`snapshot.ts`: `snapshot`, `setSnapshot`

- [ ] **Step 4: Commit**

```bash
git add app/src/bridge app/src/store
git commit -m "feat: add WebSocket client and Zustand stores"
```

### Task M4-4: Screens + ApprovalModal

**Files:**
- Create: `app/src/navigation/RootNavigator.tsx`
- Create: `app/src/screens/HomeScreen.tsx`
- Create: `app/src/screens/SessionsScreen.tsx`
- Create: `app/src/screens/SettingsScreen.tsx`
- Create: `app/src/components/ApprovalModal.tsx`
- Create: `app/src/App.tsx`

- [ ] **Step 1: RootNavigator with 3 tabs**

- [ ] **Step 2: `ApprovalModal` — show when `pending[0]` kind is `permission | single_choice | multi_choice | free_text_required` (with options)**

Approve sends:

```typescript
sendIntent({ cmd: "permission", id: pending.id, decision: "once" });
```

- [ ] **Step 3: `HomeScreen` — `GifRenderer` + `derivePetState` + connection banner**

- [ ] **Step 4: `SettingsScreen` — manual IP, mute toggle, link to PetEditor**

- [ ] **Step 5: Manual smoke test**

```bash
# Terminal 1
python3 -m bridge --transport websocket --http-port 9876 --ws-port 9877

# Terminal 2
cd app && npx expo start
```

On simulator/device (same LAN): connect to bridge IP, POST test pending via curl, confirm modal appears.

- [ ] **Step 6: Commit**

```bash
git add app/src
git commit -m "feat: add core screens and approval modal"
```

### Task M4-5: User GIF profile editor

**Files:**
- Create: `app/src/store/petProfile.ts`
- Create: `app/src/screens/PetEditorScreen.tsx`
- Create: `app/src/pet/GifRenderer.tsx`
- Create: `app/assets/default/` (placeholder GIFs per state)

- [ ] **Step 1: `petProfileStore` with persist**

```typescript
import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import AsyncStorage from "@react-native-async-storage/async-storage";
import type { PetState } from "@protocol/index";

export type PetProfile = {
  id: string;
  name: string;
  states: Partial<Record<PetState, string | null>>;
};

export const usePetProfile = create(
  persist<{ profile: PetProfile; setStateGif: (state: PetState, uri: string | null) => void }>(
    (set, get) => ({
      profile: { id: "default", name: "Buddy", states: {} },
      setStateGif: (state, uri) =>
        set({ profile: { ...get().profile, states: { ...get().profile.states, [state]: uri } } }),
    }),
    { name: "pet-profile", storage: createJSONStorage(() => AsyncStorage) },
  ),
);
```

- [ ] **Step 2: `PetEditorScreen` — pick GIF via `expo-image-picker`, copy with `expo-file-system`**

Validate extension `.gif`, size ≤ 5_000_000 bytes.

- [ ] **Step 3: `GifRenderer` — user URI or `assets/default/<state>.gif`**

- [ ] **Step 4: Commit**

```bash
git add app
git commit -m "feat: add user GIF profile editor"
```

### Task M4-6: Sounds + README finalization

**Files:**
- Create: `app/src/audio/SoundPlayer.ts`
- Modify: `README.md`

- [ ] **Step 1: SoundPlayer maps roles to bundled wav/mp3**

Play `input_required` when `pending[0]` id changes; `answer_sent` on submit.

- [ ] **Step 2: Update README — remove “planned” labels for shipped paths**

- [ ] **Step 3: Run full verification**

```bash
cd firmware && pio run
pip install -e bridge && PYTHONPATH=. python3 tools/test_bridge_http.py && python3 tools/test_bridge_ws.py
cd app && npm test
```

- [ ] **Step 4: Commit**

```bash
git add app/src/audio README.md
git commit -m "feat: add app sounds and finalize mobile README"
```

---

## Spec Coverage Checklist

| Spec requirement | Task |
| --- | --- |
| Monorepo layout `packages/ bridge/ hooks/ app/ firmware/` | M1, M2, M3, M4 |
| HTTP 9876 + WS 9877 | M2-3, M3-1 |
| mDNS `_buddy._tcp` | M3-2 |
| Reuse heartbeat + intent commands | M3-1, M4-3 |
| Cursor + Claude Code hooks | M3-3 |
| Zustand, no Query/RxJS | M4-3 |
| User GIF per state, local only | M4-5 |
| Approval UI all pending kinds | M4-4 |
| Sounds | M4-6 |
| `docs/protocol/mobile-bridge.md` | M3-1 |
| Error: reconnect, fail-open, first decision wins | M4-3, M3-1 (documented in mobile-bridge.md) |
| Firmware reference preserved | M1 |

## Out of Scope (do not implement in this plan)

- Voice notes / `audio_*` from app
- Cloud relay / push notifications
- Claude Desktop BLE proxy
- Firmware `manifest.json` import in app
- TanStack Query / RxJS

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-17-mobile-buddy-implementation.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — one fresh subagent per milestone task, review between tasks.
2. **Inline Execution** — run milestones sequentially in this session with checkpoints after M1, M2, M3, M4.

**Which approach?**
