# StickS3 Session Console Milestone A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first end-to-end StickS3 session-console loop: host bridge or simulator sends compact session JSON over BLE, firmware parses it, renders action/session screens, and sends button commands back.

**Architecture:** A local Python bridge owns session state and pending decisions, then emits backward-compatible newline-delimited JSON snapshots. StickS3 firmware remains a compact view/controller by extending `TamaState`, parsing optional rich fields, and adding a small set of screens on top of the existing pet/menu system.

**Tech Stack:** Python 3 standard library plus optional `bleak` for BLE, PlatformIO, Arduino C++, M5Unified, ArduinoJson v7, existing Nordic UART BLE bridge.

---

## File Structure

- Create `tools/session_bridge.py`: local bridge, simulator, bridge state, hook handlers, stdout/BLE transports, device command handling.
- Create `tools/test_session_bridge.py`: executable Python smoke tests for heartbeat construction, pending FIFO, commands, and hook handling.
- Create `tools/test_session_frames.py`: executable Python smoke tool that prints representative firmware frames.
- Modify `src/data.h`: add bounded session/pending/event structs, rich JSON parsing, larger line buffers, legacy fallback behavior.
- Modify `src/main.cpp`: add console screen state, render helpers, action/focus/session-list/event screens, button command routing, tone alerts.
- Modify `README.md`: add a short developer note for running the bridge simulator.
- Modify `REFERENCE.md`: document the optional rich fields without breaking the existing protocol contract.
- Use existing `tools/test_serial.py` and `tools/test_xfer.py` only for reference; do not modify them for Milestone A.

## Task 1: Baseline Build

**Files:**
- No source changes.

- [ ] **Step 1: Build current StickS3 firmware unchanged**

Run:

```bash
pio run -e m5sticks3
```

Expected: build succeeds. If it fails before any source changes, record the failure in `PROGRESS.md` before continuing.

- [ ] **Step 2: Record baseline verification**

Modify `PROGRESS.md` by adding a dated line under "Verification Done":

```markdown
- Ran `pio run -e m5sticks3` before Milestone A code changes: PASS.
```

If the build fails, write:

```markdown
- Ran `pio run -e m5sticks3` before Milestone A code changes: FAIL, <short failure summary>.
```

- [ ] **Step 3: Commit baseline documentation update**

Run:

```bash
git add PROGRESS.md
git commit -m "docs: record milestone a baseline build"
```

Expected: commit succeeds if `PROGRESS.md` changed. If the baseline note was already present, skip this commit.

## Task 2: Bridge State Model

**Files:**
- Create: `tools/test_session_bridge.py`
- Create: `tools/session_bridge.py`

- [ ] **Step 1: Write failing bridge model tests**

Create `tools/test_session_bridge.py` with:

```python
#!/usr/bin/env python3
import json
import unittest

import session_bridge


class BridgeStateTests(unittest.TestCase):
    def test_session_heartbeat_contains_legacy_and_rich_fields(self):
        state = session_bridge.BridgeState()
        state.upsert_session(
            sid="s_123",
            cwd="/tmp/claude-desktop-buddy",
            project="claude-desktop-buddy",
            branch="feature/connectors",
            dirty=2,
            phase="running",
            model="codex",
            last="editing parser",
            now=1000,
        )

        hb = state.build_heartbeat(now=1540)

        self.assertEqual(hb["total"], 1)
        self.assertEqual(hb["running"], 1)
        self.assertEqual(hb["waiting"], 0)
        self.assertEqual(hb["project"], "claude-desktop-buddy")
        self.assertEqual(hb["branch"], "feature/connectors")
        self.assertEqual(hb["sessions"][0]["sid"], "s_123")
        self.assertEqual(hb["sessions"][0]["elapsed_s"], 540)
        self.assertEqual(hb["msg"], "editing parser")

    def test_pending_fifo_and_permission_command(self):
        state = session_bridge.BridgeState()
        state.upsert_session(
            sid="s_1",
            cwd="/tmp/a",
            project="a",
            branch="main",
            dirty=0,
            phase="running",
            model="codex",
            last="working",
            now=10,
        )
        state.add_pending(
            pid="req_1",
            sid="s_1",
            kind="permission",
            title="Bash",
            body="pio run",
            options=[],
            now=20,
        )
        state.add_pending(
            pid="req_2",
            sid="s_1",
            kind="permission",
            title="Edit",
            body="src/data.h",
            options=[],
            now=21,
        )

        hb = state.build_heartbeat(now=30)
        self.assertEqual(hb["waiting"], 1)
        self.assertEqual(hb["pending"][0]["id"], "req_1")
        self.assertEqual(hb["prompt"]["id"], "req_1")

        self.assertTrue(state.handle_device_command({"cmd": "permission", "id": "req_1", "decision": "once"}))
        self.assertEqual(state.decisions["req_1"], "once")

        state.resolve_pending("req_1")
        hb = state.build_heartbeat(now=31)
        self.assertEqual(hb["pending"][0]["id"], "req_2")

    def test_focus_command_changes_focused_session(self):
        state = session_bridge.BridgeState()
        state.upsert_session("s_1", "/tmp/a", "a", "main", 0, "running", "codex", "a", now=1)
        state.upsert_session("s_2", "/tmp/b", "b", "dev", 1, "waiting", "codex", "b", now=2)

        self.assertTrue(state.handle_device_command({"cmd": "focus", "sid": "s_2"}))
        hb = state.build_heartbeat(now=3)

        self.assertEqual(hb["focused"], "s_2")
        self.assertEqual(hb["project"], "b")

    def test_json_line_is_compact_and_newline_terminated(self):
        line = session_bridge.encode_line({"total": 1, "msg": "ok"})
        self.assertTrue(line.endswith(b"\n"))
        self.assertEqual(json.loads(line.decode("utf-8")), {"total": 1, "msg": "ok"})


if __name__ == "__main__":
    unittest.main()
```

Make it executable:

```bash
chmod +x tools/test_session_bridge.py
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 tools/test_session_bridge.py
```

Expected: FAIL with `ModuleNotFoundError: No module named 'session_bridge'`.

- [ ] **Step 3: Implement bridge state model**

Create `tools/session_bridge.py` with this initial complete model:

```python
#!/usr/bin/env python3
import argparse
import json
import os
import queue
import subprocess
import sys
import threading
import time
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any


NUS_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
NUS_RX_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
NUS_TX_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"


def _clip(value: Any, n: int) -> str:
    return str(value or "").replace("\n", " ")[:n]


def encode_line(obj: dict[str, Any]) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


@dataclass
class Session:
    sid: str
    cwd: str
    project: str
    branch: str
    dirty: int
    phase: str
    model: str
    last: str
    started_at: int
    updated_at: int
    waiting_since: int = 0


@dataclass
class Pending:
    pid: str
    sid: str
    kind: str
    title: str
    body: str
    options: list[dict[str, str]] = field(default_factory=list)
    pending_since: int = 0


class BridgeState:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.sessions: OrderedDict[str, Session] = OrderedDict()
        self.pending: OrderedDict[str, Pending] = OrderedDict()
        self.decisions: dict[str, str] = {}
        self.focused_sid: str = ""
        self.entries: deque[str] = deque(maxlen=8)
        self.event: dict[str, Any] | None = None

    def upsert_session(
        self,
        sid: str,
        cwd: str,
        project: str,
        branch: str,
        dirty: int,
        phase: str,
        model: str,
        last: str,
        now: int | None = None,
    ) -> None:
        now = int(now if now is not None else time.time())
        if not sid:
            sid = f"local_{now}"
        with self.lock:
            old = self.sessions.get(sid)
            started = old.started_at if old else now
            waiting_since = old.waiting_since if old else 0
            if phase == "waiting" and waiting_since == 0:
                waiting_since = now
            if phase != "waiting":
                waiting_since = 0
            self.sessions[sid] = Session(
                sid=sid,
                cwd=cwd,
                project=_clip(project, 39),
                branch=_clip(branch, 39),
                dirty=max(0, int(dirty or 0)),
                phase=_clip(phase or "running", 16),
                model=_clip(model, 24),
                last=_clip(last, 80),
                started_at=started,
                updated_at=now,
                waiting_since=waiting_since,
            )
            if not self.focused_sid:
                self.focused_sid = sid
            if last:
                self.entries.appendleft(f"{time.strftime('%H:%M')} {_clip(last, 72)}")

    def add_pending(
        self,
        pid: str,
        sid: str,
        kind: str,
        title: str,
        body: str,
        options: list[dict[str, str]] | list[str],
        now: int | None = None,
    ) -> None:
        now = int(now if now is not None else time.time())
        normalized = []
        for i, opt in enumerate(options[:4]):
            if isinstance(opt, dict):
                oid = _clip(opt.get("id") or opt.get("label") or str(i), 20)
                label = _clip(opt.get("label") or oid, 24)
                desc = _clip(opt.get("desc") or "", 40)
            else:
                oid = str(i)
                label = _clip(opt, 24)
                desc = ""
            normalized.append({"id": oid, "label": label, "desc": desc})
        with self.lock:
            self.pending[pid] = Pending(
                pid=pid,
                sid=sid,
                kind=_clip(kind or "permission", 20),
                title=_clip(title, 40),
                body=_clip(body, 240),
                options=normalized,
                pending_since=now,
            )
            if sid in self.sessions:
                self.sessions[sid].phase = "waiting"
                self.sessions[sid].waiting_since = now

    def resolve_pending(self, pid: str) -> None:
        with self.lock:
            pending = self.pending.pop(pid, None)
            if pending and pending.sid in self.sessions:
                sess = self.sessions[pending.sid]
                sess.phase = "running"
                sess.waiting_since = 0

    def handle_device_command(self, obj: dict[str, Any]) -> bool:
        cmd = obj.get("cmd")
        with self.lock:
            if cmd == "permission":
                pid = str(obj.get("id") or "")
                decision = str(obj.get("decision") or "")
                if pid in self.pending and decision in ("once", "deny"):
                    self.decisions[pid] = decision
                    return True
                return False
            if cmd == "answer":
                pid = str(obj.get("id") or "")
                choice = str(obj.get("choice") or "")
                if pid in self.pending and choice:
                    self.decisions[pid] = choice
                    return True
                return False
            if cmd == "focus":
                sid = str(obj.get("sid") or "")
                if sid in self.sessions:
                    self.focused_sid = sid
                    return True
                return False
            if cmd == "event_dismiss":
                self.event = None
                return True
        return False

    def build_heartbeat(self, now: int | None = None) -> dict[str, Any]:
        now = int(now if now is not None else time.time())
        with self.lock:
            focused = self.sessions.get(self.focused_sid)
            if not focused and self.sessions:
                focused = next(reversed(self.sessions.values()))
                self.focused_sid = focused.sid
            active_pending = next(iter(self.pending.values()), None)
            running = sum(1 for s in self.sessions.values() if s.phase == "running")
            waiting = sum(1 for s in self.sessions.values() if s.phase == "waiting") or (1 if self.pending else 0)
            msg = active_pending.title if active_pending else (focused.last if focused else "idle")
            hb: dict[str, Any] = {
                "total": len(self.sessions),
                "running": running,
                "waiting": waiting,
                "msg": _clip(msg, 23),
                "entries": list(self.entries),
                "tokens": 0,
                "tokens_today": 0,
            }
            if focused:
                hb.update({
                    "focused": focused.sid,
                    "project": focused.project,
                    "branch": focused.branch,
                    "dirty": focused.dirty,
                    "model": focused.model,
                    "assistant_msg": focused.last,
                })
            sessions = []
            for s in list(self.sessions.values())[:5]:
                sessions.append({
                    "sid": s.sid,
                    "project": s.project,
                    "branch": s.branch,
                    "dirty": s.dirty,
                    "phase": s.phase,
                    "model": s.model,
                    "last": s.last,
                    "started_at": s.started_at,
                    "updated_at": s.updated_at,
                    "waiting_since": s.waiting_since,
                    "elapsed_s": max(0, now - s.started_at),
                    "pending_s": max(0, now - s.waiting_since) if s.waiting_since else 0,
                    "focused": s.sid == self.focused_sid,
                })
            if sessions:
                hb["sessions"] = sessions
            pending = []
            for p in list(self.pending.values())[:3]:
                pending.append({
                    "id": p.pid,
                    "sid": p.sid,
                    "kind": p.kind,
                    "title": p.title,
                    "body": p.body,
                    "pending_since": p.pending_since,
                    "pending_s": max(0, now - p.pending_since),
                    "options": p.options,
                })
            if pending:
                hb["pending"] = pending
                first = pending[0]
                hb["prompt"] = {
                    "id": first["id"],
                    "tool": _clip(first["title"], 19),
                    "hint": _clip(first["body"], 43),
                    "kind": first["kind"],
                    "body": first["body"],
                    "sid": first["sid"],
                }
            if self.event:
                hb["event"] = self.event
            return hb
```

Also add this temporary CLI stub at the end of `tools/session_bridge.py`:

```python
def main() -> int:
    state = BridgeState()
    state.upsert_session("s_demo", os.getcwd(), os.path.basename(os.getcwd()), "feature/connectors", 0, "running", "codex", "bridge ready")
    sys.stdout.buffer.write(encode_line(state.build_heartbeat()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Make it executable:

```bash
chmod +x tools/session_bridge.py
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
python3 tools/test_session_bridge.py
```

Expected: `Ran 4 tests` and `OK`.

- [ ] **Step 5: Commit**

Run:

```bash
git add tools/session_bridge.py tools/test_session_bridge.py
git commit -m "feat: add session bridge state model"
```

## Task 3: Bridge Simulator And Device Command RX

**Files:**
- Modify: `tools/session_bridge.py`
- Create: `tools/test_session_frames.py`
- Modify: `tools/test_session_bridge.py`

- [ ] **Step 1: Add failing simulator tests**

Append to `tools/test_session_bridge.py` before the `if __name__ == "__main__"` block:

```python
class SimulatorTests(unittest.TestCase):
    def test_simulator_frames_include_pending_and_event(self):
        frames = list(session_bridge.simulator_frames(now=100))
        self.assertGreaterEqual(len(frames), 3)
        self.assertIn("sessions", frames[0])
        self.assertIn("pending", frames[1])
        self.assertIn("event", frames[2])

    def test_parse_device_line_handles_json_command(self):
        state = session_bridge.BridgeState()
        state.upsert_session("s_1", "/tmp/a", "a", "main", 0, "running", "codex", "working", now=1)
        state.add_pending("req_1", "s_1", "permission", "Bash", "pio run", [], now=2)
        ok = session_bridge.handle_device_line(state, b'{"cmd":"permission","id":"req_1","decision":"deny"}\n')
        self.assertTrue(ok)
        self.assertEqual(state.decisions["req_1"], "deny")
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python3 tools/test_session_bridge.py
```

Expected: FAIL with missing `simulator_frames` or `handle_device_line`.

- [ ] **Step 3: Implement simulator frames and command parser**

Add to `tools/session_bridge.py` after `BridgeState`:

```python
def simulator_frames(now: int | None = None):
    now = int(now if now is not None else time.time())
    state = BridgeState()
    state.upsert_session(
        sid="s_demo",
        cwd=os.getcwd(),
        project=os.path.basename(os.getcwd()),
        branch=git_value(os.getcwd(), "rev-parse", "--abbrev-ref", "HEAD") or "feature/connectors",
        dirty=git_dirty(os.getcwd()),
        phase="running",
        model="codex",
        last="editing firmware UI",
        now=now - 120,
    )
    yield state.build_heartbeat(now=now)
    state.add_pending("req_demo", "s_demo", "permission", "Bash", "pio run -e m5sticks3", [], now=now - 15)
    yield state.build_heartbeat(now=now)
    state.resolve_pending("req_demo")
    state.event = {
        "kind": "complete",
        "sid": "s_demo",
        "title": "Done",
        "text": "Build finished",
        "ttl_ms": 5000,
    }
    yield state.build_heartbeat(now=now)


def handle_device_line(state: BridgeState, raw: bytes) -> bool:
    try:
        obj = json.loads(raw.decode("utf-8").strip())
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(obj, dict):
        return False
    return state.handle_device_command(obj)


def git_value(cwd: str, *args: str) -> str:
    try:
        out = subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, timeout=2, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def git_dirty(cwd: str) -> int:
    status = git_value(cwd, "status", "--porcelain")
    return sum(1 for line in status.splitlines() if line.strip())
```

Replace the temporary `main()` with:

```python
class StdoutTransport:
    def write(self, data: bytes) -> None:
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()


def run_simulator(interval: float, once: bool) -> int:
    transport = StdoutTransport()
    while True:
        for frame in simulator_frames():
            transport.write(encode_line(frame))
            if not once:
                time.sleep(interval)
        if once:
            return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--simulate", action="store_true", help="emit canned firmware frames")
    parser.add_argument("--once", action="store_true", help="emit one simulator cycle and exit")
    parser.add_argument("--interval", type=float, default=1.0)
    args = parser.parse_args()
    if args.simulate:
        return run_simulator(args.interval, args.once)
    parser.print_help()
    return 0
```

- [ ] **Step 4: Add frame smoke tool**

Create `tools/test_session_frames.py`:

```python
#!/usr/bin/env python3
import json

import session_bridge


def main() -> int:
    for frame in session_bridge.simulator_frames(now=1777180820):
        line = session_bridge.encode_line(frame).decode("utf-8").strip()
        obj = json.loads(line)
        print(line)
        assert "total" in obj
        assert "running" in obj
        assert "waiting" in obj
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Make it executable:

```bash
chmod +x tools/test_session_frames.py
```

- [ ] **Step 5: Run tests and simulator**

Run:

```bash
python3 tools/test_session_bridge.py
python3 tools/test_session_frames.py
python3 tools/session_bridge.py --simulate --once
```

Expected: tests pass, and both frame commands print newline-delimited JSON.

- [ ] **Step 6: Commit**

Run:

```bash
git add tools/session_bridge.py tools/test_session_bridge.py tools/test_session_frames.py
git commit -m "feat: add bridge simulator frames"
```

## Task 4: Bridge Hook Server And BLE Transport

**Files:**
- Modify: `tools/session_bridge.py`
- Modify: `tools/test_session_bridge.py`

- [ ] **Step 1: Add failing hook handler tests**

Append to `tools/test_session_bridge.py`:

```python
class HookHandlingTests(unittest.TestCase):
    def test_user_prompt_submit_marks_session_running(self):
        state = session_bridge.BridgeState()
        session_bridge.apply_hook(state, {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "s_1",
            "cwd": "/tmp/project",
            "prompt": "run tests",
        }, now=10)
        hb = state.build_heartbeat(now=11)
        self.assertEqual(hb["running"], 1)
        self.assertEqual(hb["sessions"][0]["phase"], "running")

    def test_pretool_adds_pending_permission(self):
        state = session_bridge.BridgeState()
        response = session_bridge.apply_hook(state, {
            "hook_event_name": "PreToolUse",
            "session_id": "s_1",
            "cwd": "/tmp/project",
            "tool_name": "Bash",
            "tool_input": {"command": "pio run -e m5sticks3"},
        }, now=20, wait_for_decision=False)
        hb = state.build_heartbeat(now=25)
        self.assertEqual(response, {})
        self.assertEqual(hb["waiting"], 1)
        self.assertEqual(hb["pending"][0]["title"], "Bash")
        self.assertIn("pio run", hb["pending"][0]["body"])

    def test_stop_creates_completion_event(self):
        state = session_bridge.BridgeState()
        state.upsert_session("s_1", "/tmp/project", "project", "main", 0, "running", "codex", "working", now=1)
        session_bridge.apply_hook(state, {
            "hook_event_name": "Stop",
            "session_id": "s_1",
            "cwd": "/tmp/project",
        }, now=30)
        hb = state.build_heartbeat(now=31)
        self.assertEqual(hb["running"], 0)
        self.assertEqual(hb["event"]["kind"], "complete")
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python3 tools/test_session_bridge.py
```

Expected: FAIL with missing `apply_hook`.

- [ ] **Step 3: Implement hook handling**

Add to `tools/session_bridge.py`:

```python
def project_name(cwd: str) -> str:
    root = git_value(cwd, "rev-parse", "--show-toplevel") if cwd and os.path.isdir(cwd) else ""
    return os.path.basename((root or cwd or "session").rstrip("/"))


def tool_body(tool: str, tin: dict[str, Any]) -> str:
    if tool == "Bash":
        desc = _clip(tin.get("description"), 120)
        command = _clip(tin.get("command"), 220)
        return f"{desc}\n$ {command}" if desc else command
    if tool in ("Edit", "MultiEdit", "Write", "Read"):
        return _clip(tin.get("file_path"), 220)
    if tool == "WebSearch":
        return _clip(tin.get("query"), 220)
    if tool == "WebFetch":
        return _clip(tin.get("url"), 220)
    return _clip(json.dumps(tin, ensure_ascii=False), 220)


def apply_hook(
    state: BridgeState,
    payload: dict[str, Any],
    now: int | None = None,
    wait_for_decision: bool = True,
    decision_timeout: float = 30.0,
) -> dict[str, Any]:
    now = int(now if now is not None else time.time())
    event = str(payload.get("hook_event_name") or "")
    sid = str(payload.get("session_id") or f"local_{now}")
    cwd = str(payload.get("cwd") or os.getcwd())
    project = project_name(cwd)
    branch = git_value(cwd, "rev-parse", "--abbrev-ref", "HEAD") or ""
    dirty = git_dirty(cwd)

    if event in ("SessionStart", "UserPromptSubmit"):
        prompt = _clip(payload.get("prompt"), 80)
        state.upsert_session(sid, cwd, project, branch, dirty, "running", _clip(payload.get("model") or "codex", 24), prompt or "running", now)
        return {}

    if event == "Stop":
        state.upsert_session(sid, cwd, project, branch, dirty, "done", _clip(payload.get("model") or "codex", 24), "session done", now)
        state.event = {"kind": "complete", "sid": sid, "title": "Done", "text": project or "Session complete", "ttl_ms": 5000}
        return {}

    if event == "Notification":
        message = _clip(payload.get("message"), 120)
        phase = "waiting" if "waiting" in message.lower() or "permission" in message.lower() else "running"
        state.upsert_session(sid, cwd, project, branch, dirty, phase, _clip(payload.get("model") or "codex", 24), message, now)
        return {}

    if event == "PreToolUse":
        if payload.get("permission_mode") == "bypassPermissions":
            return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow", "permissionDecisionReason": "bypass-permissions mode"}}
        tool = str(payload.get("tool_name") or "Tool")
        tin = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
        pid = f"req_{int(time.time() * 1000)}_{os.getpid()}"
        state.upsert_session(sid, cwd, project, branch, dirty, "waiting", _clip(payload.get("model") or "codex", 24), tool, now)
        state.add_pending(pid, sid, "permission", tool, tool_body(tool, tin), [], now)
        if not wait_for_decision:
            return {}
        deadline = time.time() + decision_timeout
        decision = ""
        while time.time() < deadline:
            with state.lock:
                decision = state.decisions.get(pid, "")
            if decision:
                break
            time.sleep(0.05)
        state.resolve_pending(pid)
        if decision == "once":
            return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow", "permissionDecisionReason": "Approved on StickS3"}}
        if decision == "deny":
            return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "Denied on StickS3"}}
        return {}

    return {}
```

- [ ] **Step 4: Implement bridge runtime skeleton**

Add to `tools/session_bridge.py`:

```python
class LineReader:
    def __init__(self, state: BridgeState) -> None:
        self.state = state
        self.buf = bytearray()

    def feed(self, data: bytes) -> None:
        for b in data:
            if b in (10, 13):
                if self.buf:
                    handle_device_line(self.state, bytes(self.buf))
                    self.buf.clear()
            elif len(self.buf) < 4096:
                self.buf.append(b)


class BridgeRuntime:
    def __init__(self, state: BridgeState, transport: Any) -> None:
        self.state = state
        self.transport = transport
        self.bump = threading.Event()
        self.stopped = threading.Event()

    def send_snapshot(self) -> None:
        self.transport.write(encode_line(self.state.build_heartbeat()))

    def heartbeat_loop(self) -> None:
        last = 0.0
        while not self.stopped.is_set():
            self.bump.wait(timeout=10.0)
            self.bump.clear()
            elapsed = time.time() - last
            if elapsed < 1.0:
                time.sleep(1.0 - elapsed)
            self.send_snapshot()
            last = time.time()
```

Replace `main()` with CLI options:

```python
def run_http(state: BridgeState, runtime: BridgeRuntime, port: int) -> HTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def do_POST(self) -> None:
            try:
                n = int(self.headers.get("Content-Length") or "0")
                payload = json.loads(self.rfile.read(n).decode("utf-8")) if n else {}
            except Exception as exc:
                body = encode_line({"error": str(exc)})
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            response = apply_hook(state, payload)
            runtime.bump.set()
            body = json.dumps(response).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return HTTPServer(("127.0.0.1", port), Handler)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--simulate", action="store_true", help="emit canned firmware frames")
    parser.add_argument("--once", action="store_true", help="emit one simulator cycle and exit")
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--http-port", type=int, default=9876)
    parser.add_argument("--transport", choices=("stdout", "ble"), default="stdout")
    args = parser.parse_args()
    if args.simulate:
        return run_simulator(args.interval, args.once)
    state = BridgeState()
    transport = StdoutTransport()
    runtime = BridgeRuntime(state, transport)
    threading.Thread(target=runtime.heartbeat_loop, daemon=True).start()
    server = run_http(state, runtime, args.http_port)
    print(f"[http] listening on 127.0.0.1:{args.http_port}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        runtime.stopped.set()
        return 0
```

- [ ] **Step 5: Add BLE transport behind optional import**

Add to `tools/session_bridge.py` before `main()`:

```python
class BLETransport:
    def __init__(self, name_prefix: str = "Claude-") -> None:
        self.name_prefix = name_prefix
        self.loop = None
        self.client = None
        self.write_queue: "queue.Queue[bytes]" = queue.Queue()

    def write(self, data: bytes) -> None:
        self.write_queue.put(data)

    def start(self, reader: LineReader) -> None:
        threading.Thread(target=self._thread_main, args=(reader,), daemon=True).start()

    def _thread_main(self, reader: LineReader) -> None:
        try:
            import asyncio
            from bleak import BleakClient, BleakScanner
        except ImportError:
            print("[ble] install bleak to use --transport ble", file=sys.stderr)
            return

        async def run() -> None:
            while True:
                device = await BleakScanner.find_device_by_filter(
                    lambda d, ad: bool(d.name) and d.name.startswith(self.name_prefix),
                    timeout=10.0,
                )
                if not device:
                    await asyncio.sleep(3.0)
                    continue
                try:
                    async with BleakClient(device) as client:
                        self.client = client

                        def on_notify(_sender, data: bytearray) -> None:
                            reader.feed(bytes(data))

                        await client.start_notify(NUS_TX_UUID, on_notify)
                        while client.is_connected:
                            try:
                                data = self.write_queue.get_nowait()
                            except queue.Empty:
                                await asyncio.sleep(0.05)
                                continue
                            await client.write_gatt_char(NUS_RX_UUID, data, response=False)
                except Exception as exc:
                    print(f"[ble] {exc!r}", file=sys.stderr)
                    await asyncio.sleep(3.0)

        asyncio.run(run())
```

Then in `main()`, replace `transport = StdoutTransport()` with:

```python
    transport = BLETransport() if args.transport == "ble" else StdoutTransport()
    reader = LineReader(state)
    if hasattr(transport, "start"):
        transport.start(reader)
```

- [ ] **Step 6: Run tests**

Run:

```bash
python3 tools/test_session_bridge.py
python3 tools/session_bridge.py --simulate --once
```

Expected: tests pass and simulator prints frames.

- [ ] **Step 7: Commit**

Run:

```bash
git add tools/session_bridge.py tools/test_session_bridge.py
git commit -m "feat: add bridge hook runtime"
```

## Task 5: Firmware Data Model And Parser

**Files:**
- Modify: `src/data.h`

- [ ] **Step 1: Add firmware structs**

In `src/data.h`, before `struct TamaState`, add:

```cpp
const uint8_t MAX_SESSIONS = 5;
const uint8_t MAX_PENDING = 3;
const uint8_t MAX_OPTIONS = 4;

struct SessionSummary {
  char sid[24];
  char project[40];
  char branch[32];
  char phase[16];
  char model[24];
  char last[80];
  int16_t dirty;
  uint32_t elapsedS;
  uint32_t pendingS;
  bool focused;
};

struct DecisionOption {
  char id[20];
  char label[28];
  char desc[44];
  bool selected;
};

struct PendingDecision {
  char id[40];
  char sid[24];
  char kind[20];
  char title[40];
  char body[120];
  uint32_t pendingS;
  DecisionOption options[MAX_OPTIONS];
  uint8_t nOptions;
  uint8_t selected;
};

struct ConsoleEvent {
  bool active;
  char kind[20];
  char sid[24];
  char title[40];
  char text[80];
  uint32_t ttlMs;
  uint32_t receivedMs;
};
```

Extend `TamaState` with:

```cpp
  char     focused[24];
  char     project[40];
  char     branch[32];
  int16_t  dirty;
  char     model[24];
  char     assistantMsg[120];
  uint32_t budget;
  SessionSummary sessions[MAX_SESSIONS];
  uint8_t  nSessions;
  PendingDecision pending[MAX_PENDING];
  uint8_t  nPending;
  ConsoleEvent event;
  uint16_t sessionGen;
  uint16_t pendingGen;
  uint16_t eventGen;
```

- [ ] **Step 2: Add bounded copy helpers**

In `src/data.h`, above `_applyJson`, add:

```cpp
static void _copyField(char* dst, size_t n, const char* src) {
  if (!dst || n == 0) return;
  if (!src) src = "";
  strncpy(dst, src, n - 1);
  dst[n - 1] = 0;
}

static uint32_t _u32(JsonVariantConst v, uint32_t fallback = 0) {
  return v.is<uint32_t>() ? v.as<uint32_t>() : fallback;
}

static int16_t _i16(JsonVariantConst v, int16_t fallback = 0) {
  return v.is<int>() ? (int16_t)v.as<int>() : fallback;
}
```

- [ ] **Step 3: Parse rich top-level fields**

In `_applyJson`, after `msg` parsing, add:

```cpp
  _copyField(out->focused, sizeof(out->focused), doc["focused"] | out->focused);
  _copyField(out->project, sizeof(out->project), doc["project"] | out->project);
  _copyField(out->branch, sizeof(out->branch), doc["branch"] | out->branch);
  out->dirty = _i16(doc["dirty"], out->dirty);
  _copyField(out->model, sizeof(out->model), doc["model"] | out->model);
  _copyField(out->assistantMsg, sizeof(out->assistantMsg), doc["assistant_msg"] | out->assistantMsg);
  out->budget = _u32(doc["budget"], out->budget);
```

- [ ] **Step 4: Parse `sessions[]`**

In `_applyJson`, before prompt parsing, add:

```cpp
  JsonArray sessions = doc["sessions"];
  if (!sessions.isNull()) {
    uint8_t n = 0;
    for (JsonObject s : sessions) {
      if (n >= MAX_SESSIONS) break;
      SessionSummary& ss = out->sessions[n];
      _copyField(ss.sid, sizeof(ss.sid), s["sid"] | "");
      _copyField(ss.project, sizeof(ss.project), s["project"] | s["proj"] | "");
      _copyField(ss.branch, sizeof(ss.branch), s["branch"] | "");
      _copyField(ss.phase, sizeof(ss.phase), s["phase"] | (s["waiting"] ? "waiting" : s["running"] ? "running" : ""));
      _copyField(ss.model, sizeof(ss.model), s["model"] | "");
      _copyField(ss.last, sizeof(ss.last), s["last"] | "");
      ss.dirty = _i16(s["dirty"], 0);
      ss.elapsedS = _u32(s["elapsed_s"], 0);
      ss.pendingS = _u32(s["pending_s"], 0);
      ss.focused = s["focused"] | false;
      n++;
    }
    if (n != out->nSessions) out->sessionGen++;
    out->nSessions = n;
  }
```

- [ ] **Step 5: Parse `pending[]` and reset selected option on queue changes**

In `_applyJson`, before legacy prompt parsing, add:

```cpp
  JsonArray pending = doc["pending"];
  if (!pending.isNull()) {
    char oldFirst[40];
    _copyField(oldFirst, sizeof(oldFirst), out->nPending ? out->pending[0].id : "");
    uint8_t n = 0;
    for (JsonObject p : pending) {
      if (n >= MAX_PENDING) break;
      PendingDecision& pd = out->pending[n];
      _copyField(pd.id, sizeof(pd.id), p["id"] | "");
      _copyField(pd.sid, sizeof(pd.sid), p["sid"] | "");
      _copyField(pd.kind, sizeof(pd.kind), p["kind"] | "permission");
      _copyField(pd.title, sizeof(pd.title), p["title"] | p["tool"] | "");
      _copyField(pd.body, sizeof(pd.body), p["body"] | p["hint"] | "");
      pd.pendingS = _u32(p["pending_s"], 0);
      JsonArray opts = p["options"];
      uint8_t oi = 0;
      for (JsonVariant opt : opts) {
        if (oi >= MAX_OPTIONS) break;
        DecisionOption& o = pd.options[oi];
        if (opt.is<const char*>()) {
          _copyField(o.id, sizeof(o.id), opt.as<const char*>());
          _copyField(o.label, sizeof(o.label), opt.as<const char*>());
          o.desc[0] = 0;
        } else {
          JsonObject oo = opt.as<JsonObject>();
          _copyField(o.id, sizeof(o.id), oo["id"] | oo["label"] | "");
          _copyField(o.label, sizeof(o.label), oo["label"] | oo["id"] | "");
          _copyField(o.desc, sizeof(o.desc), oo["desc"] | "");
        }
        o.selected = false;
        oi++;
      }
      pd.nOptions = oi;
      if (pd.selected >= pd.nOptions) pd.selected = 0;
      n++;
    }
    if (strcmp(oldFirst, n ? out->pending[0].id : "") != 0) {
      out->pendingGen++;
      if (n) out->pending[0].selected = 0;
    }
    out->nPending = n;
  }
```

- [ ] **Step 6: Parse `event`**

In `_applyJson`, before `out->lastUpdated = millis();`, add:

```cpp
  JsonObject ev = doc["event"];
  if (!ev.isNull()) {
    _copyField(out->event.kind, sizeof(out->event.kind), ev["kind"] | "");
    _copyField(out->event.sid, sizeof(out->event.sid), ev["sid"] | "");
    _copyField(out->event.title, sizeof(out->event.title), ev["title"] | "");
    _copyField(out->event.text, sizeof(out->event.text), ev["text"] | "");
    out->event.ttlMs = _u32(ev["ttl_ms"], 0);
    out->event.receivedMs = millis();
    out->event.active = out->event.kind[0] && out->event.ttlMs > 0;
    out->eventGen++;
  }
```

- [ ] **Step 7: Preserve legacy prompt fallback**

Keep the existing `prompt` parsing, but change the `else` branch so rich
pending items do not get erased:

```cpp
  } else if (out->nPending == 0) {
    out->promptId[0] = 0; out->promptTool[0] = 0; out->promptHint[0] = 0;
  }
```

After rich `pending[]` parsing, if `out->nPending > 0`, mirror the first
pending item into legacy fields:

```cpp
  if (out->nPending > 0) {
    _copyField(out->promptId, sizeof(out->promptId), out->pending[0].id);
    _copyField(out->promptTool, sizeof(out->promptTool), out->pending[0].title);
    _copyField(out->promptHint, sizeof(out->promptHint), out->pending[0].body);
  }
```

- [ ] **Step 8: Increase line buffers**

Replace:

```cpp
static _LineBuf<1024> _usbLine, _btLine;
```

with:

```cpp
static _LineBuf<2560> _usbLine, _btLine;
```

- [ ] **Step 9: Build firmware**

Run:

```bash
pio run -e m5sticks3
```

Expected: build succeeds.

- [ ] **Step 10: Commit**

Run:

```bash
git add src/data.h
git commit -m "feat: parse session console state"
```

## Task 6: Firmware Action And Focused Session Screens

**Files:**
- Modify: `src/main.cpp`

- [ ] **Step 1: Add console display modes and indexes**

Replace:

```cpp
enum DisplayMode { DISP_NORMAL, DISP_PET, DISP_INFO, DISP_COUNT };
```

with:

```cpp
enum DisplayMode { DISP_NORMAL, DISP_SESSION, DISP_SESSIONS, DISP_PET, DISP_INFO, DISP_COUNT };
```

Add near `msgScroll`:

```cpp
uint8_t sessionPage = 0;
uint16_t lastPendingGen = 0;
uint16_t lastEventGen = 0;
```

- [ ] **Step 2: Add duration formatting helper**

Add before `drawApproval()`:

```cpp
static void fmtDur(uint32_t s, char* out, size_t n) {
  if (s < 60) snprintf(out, n, "%lus", (unsigned long)s);
  else if (s < 3600) snprintf(out, n, "%lum", (unsigned long)(s / 60));
  else snprintf(out, n, "%luh%02lum", (unsigned long)(s / 3600), (unsigned long)((s / 60) % 60));
}
```

- [ ] **Step 3: Add rich action renderer**

Add before existing `drawApproval()`:

```cpp
static void drawAction() {
  if (tama.nPending == 0) { drawApproval(); return; }
  const Palette& p = characterPalette();
  PendingDecision& d = tama.pending[0];
  const int AREA = 104;
  spr.fillRect(0, H - AREA, W, AREA, p.bg);
  spr.drawFastHLine(0, H - AREA, W, p.textDim);
  spr.setTextSize(1);

  char age[12]; fmtDur(d.pendingS ? d.pendingS : ((millis() - promptArrivedMs) / 1000), age, sizeof(age));
  spr.setTextColor(HOT, p.bg);
  spr.setCursor(4, H - AREA + 4);
  spr.printf("%s  wait %s", d.kind[0] ? d.kind : "action", age);

  spr.setTextColor(p.text, p.bg);
  spr.setTextSize(strlen(d.title) <= 10 ? 2 : 1);
  spr.setCursor(4, H - AREA + 18);
  spr.print(d.title[0] ? d.title : "Decision");
  spr.setTextSize(1);

  spr.setTextColor(p.textDim, p.bg);
  spr.setCursor(4, H - AREA + 40);
  spr.printf("%.21s", d.body);
  if (strlen(d.body) > 21) {
    spr.setCursor(4, H - AREA + 50);
    spr.printf("%.21s", d.body + 21);
  }

  if (strcmp(d.kind, "single_choice") == 0 && d.nOptions > 0) {
    DecisionOption& opt = d.options[d.selected];
    spr.setTextColor(p.body, p.bg);
    spr.setCursor(4, H - 30);
    spr.printf("%u/%u %.16s", d.selected + 1, d.nOptions, opt.label);
    spr.setTextColor(GREEN, p.bg);
    spr.setCursor(4, H - 12); spr.print("A: choose");
    spr.setTextColor(p.textDim, p.bg);
    spr.setCursor(W - 42, H - 12); spr.print("B: next");
  } else if (responseSent) {
    spr.setTextColor(p.textDim, p.bg);
    spr.setCursor(4, H - 12); spr.print("sent...");
  } else {
    spr.setTextColor(GREEN, p.bg);
    spr.setCursor(4, H - 12); spr.print("A: approve");
    spr.setTextColor(HOT, p.bg);
    spr.setCursor(W - 48, H - 12); spr.print("B: deny");
  }
}
```

- [ ] **Step 4: Route HUD to rich action screen**

Replace the first line of `drawHUD()`:

```cpp
  if (tama.promptId[0]) { drawApproval(); return; }
```

with:

```cpp
  if (tama.promptId[0] || tama.nPending > 0) { drawAction(); return; }
```

- [ ] **Step 5: Add focused session renderer**

Add after `drawHUD()`:

```cpp
static void drawFocusedSession() {
  const Palette& p = characterPalette();
  const int TOP = 70;
  spr.fillRect(0, TOP, W, H - TOP, p.bg);
  spr.setTextSize(1);

  SessionSummary* s = nullptr;
  for (uint8_t i = 0; i < tama.nSessions; i++) {
    if (tama.sessions[i].focused) { s = &tama.sessions[i]; break; }
  }
  if (!s && tama.nSessions > 0) s = &tama.sessions[0];

  int y = TOP + 2;
  spr.setTextColor(p.text, p.bg);
  spr.setCursor(4, y); spr.print("Session"); y += 12;

  if (!s) {
    spr.setTextColor(p.textDim, p.bg);
    spr.setCursor(4, y); spr.print(tama.connected ? "No sessions" : "No bridge");
    return;
  }

  char dur[12]; fmtDur(s->pendingS ? s->pendingS : s->elapsedS, dur, sizeof(dur));
  spr.setTextColor(p.body, p.bg);
  spr.setCursor(4, y); spr.printf("%.21s", s->project[0] ? s->project : tama.project); y += 12;
  spr.setTextColor(p.textDim, p.bg);
  spr.setCursor(4, y); spr.printf("%.21s", s->branch[0] ? s->branch : tama.branch); y += 12;
  spr.setCursor(4, y); spr.printf("%s %s  dirty %d", s->phase, dur, s->dirty); y += 12;
  spr.setCursor(4, y); spr.printf("model %.16s", s->model[0] ? s->model : tama.model); y += 16;
  spr.setTextColor(p.text, p.bg);
  spr.setCursor(4, y); spr.printf("%.21s", s->last[0] ? s->last : tama.assistantMsg); y += 10;
  if (strlen(s->last[0] ? s->last : tama.assistantMsg) > 21) {
    spr.setCursor(4, y); spr.printf("%.21s", (s->last[0] ? s->last : tama.assistantMsg) + 21);
  }
}
```

- [ ] **Step 6: Add session list renderer**

Add after `drawFocusedSession()`:

```cpp
static void drawSessionList() {
  const Palette& p = characterPalette();
  const int TOP = 70;
  spr.fillRect(0, TOP, W, H - TOP, p.bg);
  spr.setTextSize(1);
  int y = TOP + 2;
  spr.setTextColor(p.text, p.bg);
  spr.setCursor(4, y); spr.print("Sessions");
  spr.setTextColor(p.textDim, p.bg);
  spr.setCursor(W - 28, y); spr.printf("%u/%u", tama.nSessions ? sessionPage + 1 : 0, tama.nSessions);
  y += 16;

  if (tama.nSessions == 0) {
    spr.setTextColor(p.textDim, p.bg);
    spr.setCursor(4, y); spr.print("No sessions");
    return;
  }
  if (sessionPage >= tama.nSessions) sessionPage = 0;
  SessionSummary& s = tama.sessions[sessionPage];
  char dur[12]; fmtDur(s.pendingS ? s.pendingS : s.elapsedS, dur, sizeof(dur));
  spr.setTextColor(s.focused ? GREEN : p.body, p.bg);
  spr.setCursor(4, y); spr.printf("%.21s", s.project); y += 12;
  spr.setTextColor(p.textDim, p.bg);
  spr.setCursor(4, y); spr.printf("%.21s", s.branch); y += 12;
  spr.setCursor(4, y); spr.printf("%s %s", s.phase, dur); y += 16;
  spr.setTextColor(p.text, p.bg);
  spr.setCursor(4, y); spr.printf("%.21s", s.last);
  spr.setTextColor(GREEN, p.bg);
  spr.setCursor(4, H - 12); spr.print("A: focus");
  spr.setTextColor(p.textDim, p.bg);
  spr.setCursor(W - 42, H - 12); spr.print("B: next");
}
```

- [ ] **Step 7: Render new modes**

In the final render section, replace:

```cpp
    else if (displayMode == DISP_INFO) drawInfo();
    else if (displayMode == DISP_PET) drawPet();
    else if (settings().hud) drawHUD();
```

with:

```cpp
    else if (displayMode == DISP_INFO) drawInfo();
    else if (displayMode == DISP_PET) drawPet();
    else if (displayMode == DISP_SESSION) drawFocusedSession();
    else if (displayMode == DISP_SESSIONS) drawSessionList();
    else if (settings().hud) drawHUD();
```

- [ ] **Step 8: Build firmware**

Run:

```bash
pio run -e m5sticks3
```

Expected: build succeeds.

- [ ] **Step 9: Commit**

Run:

```bash
git add src/main.cpp
git commit -m "feat: add session console screens"
```

## Task 7: Firmware Button Commands And Tone Alerts

**Files:**
- Modify: `src/main.cpp`

- [ ] **Step 1: Add JSON command helpers**

Add near `sendCmd`:

```cpp
static void sendPermissionDecision(const char* id, const char* decision) {
  char cmd[128];
  snprintf(cmd, sizeof(cmd), "{\"cmd\":\"permission\",\"id\":\"%s\",\"decision\":\"%s\"}", id, decision);
  sendCmd(cmd);
}

static void sendAnswerChoice(const char* id, const char* choice) {
  char cmd[144];
  snprintf(cmd, sizeof(cmd), "{\"cmd\":\"answer\",\"id\":\"%s\",\"choice\":\"%s\"}", id, choice);
  sendCmd(cmd);
}

static void sendFocusSession(const char* sid) {
  char cmd[96];
  snprintf(cmd, sizeof(cmd), "{\"cmd\":\"focus\",\"sid\":\"%s\"}", sid);
  sendCmd(cmd);
}
```

- [ ] **Step 2: Add alert tones for pending and events**

In the loop after prompt-arrival handling, add:

```cpp
  if (tama.pendingGen != lastPendingGen) {
    lastPendingGen = tama.pendingGen;
    if (tama.nPending > 0) {
      wake();
      beep(1200, 80);
    }
  }
  if (tama.eventGen != lastEventGen) {
    lastEventGen = tama.eventGen;
    if (tama.event.active) {
      if (strcmp(tama.event.kind, "error") == 0) beep(500, 120);
      else if (strcmp(tama.event.kind, "complete") == 0) { beep(1600, 60); delay(80); beep(2200, 60); }
      else beep(1000, 60);
    }
  }
```

- [ ] **Step 3: Update A release behavior**

In `if (M5.BtnA.wasReleased())`, replace the `if (inPrompt)` block with:

```cpp
      if (inPrompt) {
        if (tama.nPending > 0 && strcmp(tama.pending[0].kind, "single_choice") == 0 && tama.pending[0].nOptions > 0) {
          PendingDecision& d = tama.pending[0];
          sendAnswerChoice(d.id, d.options[d.selected].id);
        } else {
          sendPermissionDecision(tama.promptId, "once");
          uint32_t tookS = (millis() - promptArrivedMs) / 1000;
          statsOnApproval(tookS);
          if (tookS < 5) triggerOneShot(P_HEART, 2000);
        }
        responseSent = true;
        beep(2400, 60);
      } else if (displayMode == DISP_SESSIONS && tama.nSessions > 0) {
        sendFocusSession(tama.sessions[sessionPage].sid);
        displayMode = DISP_SESSION;
        applyDisplayMode();
```

Keep the existing `else if (resetOpen)` and following branches after this
new block.

- [ ] **Step 4: Update B press behavior**

In `if (M5.BtnB.wasPressed())`, replace the `if (inPrompt)` block with:

```cpp
    if (inPrompt) {
      if (tama.nPending > 0 && strcmp(tama.pending[0].kind, "single_choice") == 0 && tama.pending[0].nOptions > 0) {
        PendingDecision& d = tama.pending[0];
        d.selected = (d.selected + 1) % d.nOptions;
        beep(1800, 30);
      } else {
        sendPermissionDecision(tama.promptId, "deny");
        responseSent = true;
        statsOnDenial();
        beep(600, 60);
      }
    } else if (displayMode == DISP_SESSIONS && tama.nSessions > 0) {
      beep(2400, 30);
      sessionPage = (sessionPage + 1) % tama.nSessions;
      applyDisplayMode();
```

Keep the existing `else if (resetOpen)` and following branches after this
new block.

- [ ] **Step 5: Build firmware**

Run:

```bash
pio run -e m5sticks3
```

Expected: build succeeds.

- [ ] **Step 6: Commit**

Run:

```bash
git add src/main.cpp
git commit -m "feat: wire session console buttons"
```

## Task 8: Event Overlay

**Files:**
- Modify: `src/main.cpp`

- [ ] **Step 1: Add event active helper**

Add before draw functions:

```cpp
static bool eventVisible() {
  return tama.event.active
      && tama.event.ttlMs > 0
      && (millis() - tama.event.receivedMs) < tama.event.ttlMs
      && !tama.promptId[0]
      && tama.nPending == 0;
}
```

- [ ] **Step 2: Add event renderer**

Add after `drawSessionList()`:

```cpp
static void drawEventOverlay() {
  const Palette& p = characterPalette();
  uint32_t age = millis() - tama.event.receivedMs;
  uint32_t left = (age < tama.event.ttlMs) ? (tama.event.ttlMs - age) : 0;
  int mw = 118, mh = 72;
  int mx = (W - mw) / 2, my = H - mh - 10;
  spr.fillRoundRect(mx, my, mw, mh, 4, PANEL);
  spr.drawRoundRect(mx, my, mw, mh, 4, strcmp(tama.event.kind, "error") == 0 ? HOT : GREEN);
  spr.setTextSize(1);
  spr.setTextColor(p.text, PANEL);
  spr.setCursor(mx + 6, my + 8);
  spr.printf("%.17s", tama.event.title[0] ? tama.event.title : tama.event.kind);
  spr.setTextColor(p.textDim, PANEL);
  spr.setCursor(mx + 6, my + 24);
  spr.printf("%.17s", tama.event.text);
  if (strlen(tama.event.text) > 17) {
    spr.setCursor(mx + 6, my + 34);
    spr.printf("%.17s", tama.event.text + 17);
  }
  int barW = mw - 12;
  spr.drawRect(mx + 6, my + mh - 14, barW, 5, p.textDim);
  int fill = tama.event.ttlMs ? (int)((uint64_t)barW * left / tama.event.ttlMs) : 0;
  if (fill > 0) spr.fillRect(mx + 7, my + mh - 13, fill - 2, 3, p.body);
}
```

- [ ] **Step 3: Render overlay last before menus**

In the final render section before reset/settings/menu overlays, add:

```cpp
    if (eventVisible()) drawEventOverlay();
```

- [ ] **Step 4: Allow B to dismiss event**

In `if (M5.BtnB.wasPressed())`, before the final normal-mode transcript scroll branch, add:

```cpp
    } else if (eventVisible()) {
      tama.event.active = false;
      sendCmd("{\"cmd\":\"event_dismiss\",\"sid\":\"\"}");
      beep(1200, 30);
```

- [ ] **Step 5: Build firmware**

Run:

```bash
pio run -e m5sticks3
```

Expected: build succeeds.

- [ ] **Step 6: Commit**

Run:

```bash
git add src/main.cpp
git commit -m "feat: add session event overlay"
```

## Task 9: Protocol And Usage Documentation

**Files:**
- Modify: `README.md`
- Modify: `REFERENCE.md`
- Modify: `PROGRESS.md`

- [ ] **Step 1: Update `REFERENCE.md` rich heartbeat section**

After the existing heartbeat field table, add:

```markdown
### Optional session-console fields

Newer firmware can also consume optional multi-session fields. Older
devices ignore them.

| Field | Meaning |
| --- | --- |
| `focused` | Host-selected session id currently shown as primary |
| `project` | Focused session project name |
| `branch` | Focused session git branch |
| `dirty` | Focused session dirty file count |
| `model` | Short model or agent label |
| `assistant_msg` | Short host-provided latest message summary |
| `budget` | Optional context budget for display |
| `sessions[]` | Bounded compact session summaries |
| `pending[]` | Bounded pending decisions, highest priority first |
| `event` | Short-lived completion/error/input-required overlay |

Devices should prefer `pending[0]` for an action screen and fall back to
legacy `prompt` when `pending[]` is absent.
```

- [ ] **Step 2: Update `README.md` bridge simulator note**

Under "Build, Test, and Development Commands" or near `tools/`, add:

````markdown
For local session-console bring-up without Claude/Codex hooks:

```bash
python3 tools/session_bridge.py --simulate --once
python3 tools/test_session_bridge.py
python3 tools/test_session_frames.py
```

Use `python3 tools/session_bridge.py --transport ble` for the live bridge
once a StickS3 is paired.
````

- [ ] **Step 3: Update `PROGRESS.md`**

Add completed implementation bullets and verification commands actually
run. Use this format:

```markdown
- Implemented Milestone A host bridge simulator and state model.
- Extended firmware parser and compact session-console screens.
- Verification:
  - `python3 tools/test_session_bridge.py`: PASS
  - `python3 tools/test_session_frames.py`: PASS
  - `pio run -e m5sticks3`: PASS
```

- [ ] **Step 4: Commit**

Run:

```bash
git add README.md REFERENCE.md PROGRESS.md
git commit -m "docs: document session console protocol"
```

## Task 10: End-To-End Verification

**Files:**
- No source changes unless verification exposes a bug.

- [ ] **Step 1: Run host tests**

Run:

```bash
python3 tools/test_session_bridge.py
python3 tools/test_session_frames.py
```

Expected: both pass.

- [ ] **Step 2: Run firmware build**

Run:

```bash
pio run -e m5sticks3
```

Expected: build succeeds.

- [ ] **Step 3: Flash hardware**

Run:

```bash
pio run -e m5sticks3 -t upload
```

Expected: upload succeeds. If manual download mode is required, follow the StickS3 instructions from `docs/sticks3-plus-reference.md`.

- [ ] **Step 4: Pair BLE and run simulator**

Run:

```bash
python3 tools/session_bridge.py --transport ble --simulate
```

Expected:

- StickS3 receives frames over BLE.
- Focused session screen shows project/branch/phase.
- Pending permission appears and plays a tone.
- `A` sends approve command to bridge logs.
- `B` sends deny or cycles options depending on decision kind.
- Completion event shows a countdown overlay.

- [ ] **Step 5: Record hardware verification**

Modify `PROGRESS.md` with exact board and command results:

```markdown
- Hardware verification on M5 StickS3:
  - BLE pairing: PASS
  - Simulator heartbeat display: PASS
  - Pending permission display: PASS
  - A approve command: PASS
  - B deny command: PASS
  - Event overlay: PASS
  - Tone alerts: PASS
```

If any item fails, write `FAIL` and a one-line symptom.

- [ ] **Step 6: Final commit**

Run:

```bash
git add PROGRESS.md
git commit -m "test: verify session console milestone a"
```

## Plan Self-Review Notes

- Spec coverage: host bridge, simulator, rich protocol, firmware parser, action/focused/session-list screens, tones, documentation, and verification are all mapped to tasks.
- Scope control: CJK, WAV, microphone, WiFi, USB RX, and host persistence are excluded from implementation tasks.
- Type consistency: plan uses `sessions[]`, `pending[]`, `event`, `focused`, `permission`, `answer`, `focus`, and `event_dismiss` consistently with the design spec.
