#!/usr/bin/env python3
import argparse
import glob
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


def chunk_bytes(data: bytes, max_size: int):
    if max_size <= 0:
        raise ValueError("max_size must be positive")
    for start in range(0, len(data), max_size):
        yield data[start:start + max_size]


def serial_port_candidates(globber: Any = glob.glob) -> list[str]:
    ports: list[str] = []
    for pattern in (
        "/dev/tty.usbmodem*",
        "/dev/cu.usbmodem*",
        "/dev/tty.usbserial-*",
        "/dev/cu.usbserial-*",
    ):
        ports.extend(sorted(globber(pattern)))
    return ports


def pick_serial_port(explicit: str = "", globber: Any = glob.glob) -> str:
    if explicit:
        return explicit
    ports = serial_port_candidates(globber)
    return ports[0] if ports else ""


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
        self.decisions: dict[str, Any] = {}
        self.focused_sid: str = ""
        self.entries: deque[str] = deque(maxlen=8)
        self.event: dict[str, Any] | None = None

    def _oldest_pending_since(self, sid: str) -> int:
        times = [p.pending_since for p in self.pending.values() if p.sid == sid]
        return min(times) if times else 0

    def clear_pending_for_session(self, sid: str) -> None:
        with self.lock:
            removed = [pid for pid, pending in self.pending.items() if pending.sid == sid]
            for pid in removed:
                self.pending.pop(pid, None)
                self.decisions.pop(pid, None)
            sess = self.sessions.get(sid)
            if not sess:
                return
            sess.waiting_since = 0
            if sess.phase == "waiting":
                sess.phase = "running"

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
            pending_since = self._oldest_pending_since(sid)
            if pending_since:
                phase = "waiting"
                waiting_since = pending_since
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
                self.sessions[sid].waiting_since = self._oldest_pending_since(sid)

    def resolve_pending(self, pid: str) -> None:
        with self.lock:
            pending = self.pending.pop(pid, None)
            if pending and pending.sid in self.sessions:
                sess = self.sessions[pending.sid]
                pending_since = self._oldest_pending_since(pending.sid)
                if pending_since:
                    sess.phase = "waiting"
                    sess.waiting_since = pending_since
                else:
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
                pending = self.pending.get(pid)
                choice = str(obj.get("choice") or "")
                if pending and pending.kind == "single_choice" and choice:
                    if any(opt.get("id") == choice for opt in pending.options):
                        self.decisions[pid] = choice
                        return True
                raw_choices = obj.get("choices")
                if pending and pending.kind == "multi_choice" and isinstance(raw_choices, list):
                    allowed = {opt.get("id") for opt in pending.options}
                    seen: set[str] = set()
                    selected: list[str] = []
                    for raw in raw_choices:
                        if not isinstance(raw, str) or not raw:
                            return False
                        if raw in seen or raw not in allowed:
                            return False
                        seen.add(raw)
                        selected.append(raw)
                    if selected:
                        self.decisions[pid] = selected
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


def _sim_permission_pending(state: BridgeState, now: int) -> None:
    state.add_pending("req_demo", "s_demo", "permission", "Bash", "pio run -e m5sticks3", [], now=now - 15)


def _sim_single_pending(state: BridgeState, now: int) -> None:
    state.add_pending(
        "choice_demo",
        "s_demo",
        "single_choice",
        "Transport",
        "pick transport",
        [
            {"id": "ble", "label": "BLE", "desc": "Wireless"},
            {"id": "usb", "label": "USB", "desc": "Serial"},
            {"id": "wifi", "label": "WiFi", "desc": "Later"},
        ],
        now=now - 15,
    )


def _sim_multi_pending(state: BridgeState, now: int) -> None:
    state.add_pending(
        "multi_demo",
        "s_demo",
        "multi_choice",
        "Transport",
        "pick one or more",
        [
            {"id": "ble", "label": "BLE", "desc": "Wireless"},
            {"id": "usb", "label": "USB", "desc": "Serial"},
            {"id": "wifi", "label": "WiFi", "desc": "Later"},
        ],
        now=now - 15,
    )


def simulator_frames(now: int | None = None, profile: str = "permission"):
    now = int(now if now is not None else time.time())
    cwd = os.getcwd()
    state = BridgeState()
    state.upsert_session(
        sid="s_demo",
        cwd=cwd,
        project=os.path.basename(cwd),
        branch=git_value(cwd, "rev-parse", "--abbrev-ref", "HEAD") or "feature/connectors",
        dirty=git_dirty(cwd),
        phase="running",
        model="codex",
        last="editing firmware UI",
        now=now - 120,
    )
    yield state.build_heartbeat(now=now)
    if profile == "single":
        _sim_single_pending(state, now)
        yield state.build_heartbeat(now=now)
        state.resolve_pending("choice_demo")
        state.event = {
            "kind": "complete",
            "sid": "s_demo",
            "title": "Saved",
            "text": "Choice submitted",
            "ttl_ms": 5000,
        }
        yield state.build_heartbeat(now=now)
        return
    if profile == "multi":
        _sim_multi_pending(state, now)
        yield state.build_heartbeat(now=now)
        state.resolve_pending("multi_demo")
        state.event = {
            "kind": "complete",
            "sid": "s_demo",
            "title": "Saved",
            "text": "Choices submitted",
            "ttl_ms": 5000,
        }
        yield state.build_heartbeat(now=now)
        return
    _sim_permission_pending(state, now)
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


def seed_simulator_state(state: BridgeState, now: int | None = None) -> None:
    now = int(now if now is not None else time.time())
    cwd = os.getcwd()
    state.upsert_session(
        sid="s_demo",
        cwd=cwd,
        project=os.path.basename(cwd),
        branch=git_value(cwd, "rev-parse", "--abbrev-ref", "HEAD") or "feature/connectors",
        dirty=git_dirty(cwd),
        phase="running",
        model="codex",
        last="editing firmware UI",
        now=now - 120,
    )


def publish_simulator_decision_cycle(state: BridgeState, transport: Any, interval: float, profile: str = "permission") -> None:
    now = int(time.time())
    seed_simulator_state(state, now=now)
    transport.write(encode_line(state.build_heartbeat(now=now)))

    if profile == "single":
        pending_id = "choice_demo"
        _sim_single_pending(state, now)
        transport.write(encode_line(state.build_heartbeat(now=now)))

        decision = ""
        while not decision:
            with state.lock:
                raw = state.decisions.pop(pending_id, "")
                decision = raw if isinstance(raw, str) else ""
            if decision:
                break
            time.sleep(interval)
            transport.write(encode_line(state.build_heartbeat(now=int(time.time()))))

        state.resolve_pending(pending_id)
        state.event = {
            "kind": "complete",
            "sid": "s_demo",
            "title": "Saved",
            "text": f"Choice {decision}",
            "ttl_ms": 5000,
        }
        print(f"[sim] choice={decision}", file=sys.stderr)
        transport.write(encode_line(state.build_heartbeat(now=int(time.time()))))
        return
    if profile == "multi":
        pending_id = "multi_demo"
        _sim_multi_pending(state, now)
        transport.write(encode_line(state.build_heartbeat(now=now)))

        decision: list[str] = []
        while not decision:
            with state.lock:
                raw = state.decisions.pop(pending_id, [])
                decision = raw if isinstance(raw, list) else []
            if decision:
                break
            time.sleep(interval)
            transport.write(encode_line(state.build_heartbeat(now=int(time.time()))))

        state.resolve_pending(pending_id)
        state.event = {
            "kind": "complete",
            "sid": "s_demo",
            "title": "Saved",
            "text": ",".join(decision),
            "ttl_ms": 5000,
        }
        print(f"[sim] choices={decision}", file=sys.stderr)
        transport.write(encode_line(state.build_heartbeat(now=int(time.time()))))
        return

    pending_id = "req_demo"
    _sim_permission_pending(state, now)
    transport.write(encode_line(state.build_heartbeat(now=now)))

    decision = ""
    while not decision:
        with state.lock:
            raw = state.decisions.pop(pending_id, "")
            decision = raw if isinstance(raw, str) else ""
        if decision:
            break
        time.sleep(interval)
        transport.write(encode_line(state.build_heartbeat(now=int(time.time()))))

    state.resolve_pending(pending_id)
    approved = decision == "once"
    state.event = {
        "kind": "complete" if approved else "error",
        "sid": "s_demo",
        "title": "Done" if approved else "Denied",
        "text": "Build finished" if approved else "Request denied",
        "ttl_ms": 5000,
    }
    print(f"[sim] decision={decision}", file=sys.stderr)
    transport.write(encode_line(state.build_heartbeat(now=int(time.time()))))


def git_value(cwd: str, *args: str) -> str:
    try:
        out = subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, timeout=2, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def git_dirty(cwd: str) -> int:
    status = git_value(cwd, "status", "--porcelain")
    return sum(1 for line in status.splitlines() if line.strip())


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
    on_state_change: Any = None,
) -> dict[str, Any]:
    def notify_state_change() -> None:
        if on_state_change:
            on_state_change()

    now = int(now if now is not None else time.time())
    event = str(payload.get("hook_event_name") or "")
    sid = str(payload.get("session_id") or f"local_{now}")
    cwd = str(payload.get("cwd") or os.getcwd())
    project = project_name(cwd)
    branch = git_value(cwd, "rev-parse", "--abbrev-ref", "HEAD") or ""
    dirty = git_dirty(cwd)
    model = _clip(payload.get("model") or "codex", 24)

    if event in ("SessionStart", "UserPromptSubmit"):
        prompt = _clip(payload.get("prompt"), 80)
        state.upsert_session(sid, cwd, project, branch, dirty, "running", model, prompt or "running", now)
        notify_state_change()
        return {}

    if event == "Stop":
        state.clear_pending_for_session(sid)
        state.upsert_session(sid, cwd, project, branch, dirty, "done", model, "session done", now)
        with state.lock:
            state.event = {
                "kind": "complete",
                "sid": sid,
                "title": "Done",
                "text": project or "Session complete",
                "ttl_ms": 5000,
            }
        notify_state_change()
        return {}

    if event == "Notification":
        message = _clip(payload.get("message"), 120)
        lower = message.lower()
        phase = "waiting" if "waiting" in lower or "permission" in lower else "running"
        state.upsert_session(sid, cwd, project, branch, dirty, phase, model, message, now)
        notify_state_change()
        return {}

    if event == "PreToolUse":
        if payload.get("permission_mode") == "bypassPermissions":
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": "bypass-permissions mode",
                }
            }
        tool = str(payload.get("tool_name") or "Tool")
        tin = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
        pid = f"req_{int(time.time() * 1000)}_{os.getpid()}"
        state.upsert_session(sid, cwd, project, branch, dirty, "waiting", model, tool, now)
        state.add_pending(pid, sid, "permission", tool, tool_body(tool, tin), [], now)
        notify_state_change()
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
        notify_state_change()
        if decision == "once":
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": "Approved on StickS3",
                }
            }
        if decision == "deny":
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": "Denied on StickS3",
                }
            }
        return {}

    return {}


class StdoutTransport:
    def write(self, data: bytes) -> None:
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()


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
            response = apply_hook(state, payload, on_state_change=runtime.bump.set)
            runtime.bump.set()
            body = json.dumps(response).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return HTTPServer(("127.0.0.1", port), Handler)


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
                            for chunk in chunk_bytes(data, 180):
                                await client.write_gatt_char(NUS_RX_UUID, chunk, response=False)
                                await asyncio.sleep(0)
                except Exception as exc:
                    print(f"[ble] {exc!r}", file=sys.stderr)
                    await asyncio.sleep(3.0)

        asyncio.run(run())


class SerialTransport:
    def __init__(self, port: str = "", baud: int = 115200, settle: float = 1.0) -> None:
        self.port = port
        self.baud = baud
        self.settle = settle
        self.write_queue: "queue.Queue[bytes]" = queue.Queue()

    def write(self, data: bytes) -> None:
        self.write_queue.put(data)

    def start(self, reader: LineReader) -> None:
        threading.Thread(target=self._thread_main, args=(reader,), daemon=True).start()

    def _thread_main(self, reader: LineReader) -> None:
        try:
            import serial
        except ImportError:
            print("[serial] install pyserial to use --transport serial", file=sys.stderr)
            return

        while True:
            port = pick_serial_port(self.port)
            if not port:
                print("[serial] no compatible USB serial device found", file=sys.stderr)
                time.sleep(2.0)
                continue
            try:
                with serial.Serial(port, self.baud, timeout=0.1, write_timeout=1) as dev:
                    print(f"[serial] connected {port}", file=sys.stderr)
                    time.sleep(self.settle)
                    while True:
                        try:
                            data = self.write_queue.get(timeout=0.05)
                        except queue.Empty:
                            data = b""
                        if data:
                            dev.write(data)
                            dev.flush()
                        waiting = dev.in_waiting if hasattr(dev, "in_waiting") else 0
                        if waiting:
                            chunk = dev.read(waiting)
                            if chunk:
                                reader.feed(chunk)
            except Exception as exc:
                print(f"[serial] {exc!r}", file=sys.stderr)
                time.sleep(1.0)


def run_simulator(interval: float, once: bool, transport: Any | None = None, profile: str = "permission") -> int:
    state = BridgeState()
    reader = LineReader(state)
    transport = transport or StdoutTransport()
    if hasattr(transport, "start"):
        transport.start(reader)
    if once:
        for frame in simulator_frames(profile=profile):
            transport.write(encode_line(frame))
            time.sleep(interval)
        if hasattr(transport, "start"):
            time.sleep(max(interval, 0.5))
        return 0
    while True:
        publish_simulator_decision_cycle(state, transport, max(interval, 0.25), profile=profile)
        time.sleep(interval)
        with state.lock:
            state.pending.clear()
            state.decisions.clear()
            state.event = None
            sess = state.sessions.get("s_demo")
            if sess:
                sess.phase = "running"
                sess.waiting_since = 0
        transport.write(encode_line(state.build_heartbeat(now=int(time.time()))))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--simulate", action="store_true", help="emit canned firmware frames")
    parser.add_argument("--once", action="store_true", help="emit one simulator cycle and exit")
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--http-port", type=int, default=9876)
    parser.add_argument("--simulate-profile", choices=("permission", "single", "multi"), default="permission")
    parser.add_argument("--transport", choices=("stdout", "ble", "serial"), default="stdout")
    parser.add_argument("--serial-port", default="", help="USB serial device path")
    parser.add_argument("--serial-baud", type=int, default=115200)
    args = parser.parse_args()
    if args.transport == "ble":
        transport = BLETransport()
    elif args.transport == "serial":
        transport = SerialTransport(port=args.serial_port, baud=args.serial_baud)
    else:
        transport = StdoutTransport()
    if args.simulate:
        return run_simulator(args.interval, args.once, transport=transport, profile=args.simulate_profile)
    state = BridgeState()
    reader = LineReader(state)
    if hasattr(transport, "start"):
        transport.start(reader)
    runtime = BridgeRuntime(state, transport)
    threading.Thread(target=runtime.heartbeat_loop, daemon=True).start()
    server = run_http(state, runtime, args.http_port)
    print(f"[http] listening on 127.0.0.1:{args.http_port}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        runtime.stopped.set()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
