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
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
from typing import Any

from bridge.core.state import AudioUpload, BridgeState, Pending, Session


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
        state.set_event({
            "kind": "complete",
            "sid": "s_demo",
            "title": "Saved",
            "text": "Choice submitted",
            "ttl_ms": 5000,
        })
        yield state.build_heartbeat(now=now)
        return
    if profile == "multi":
        _sim_multi_pending(state, now)
        yield state.build_heartbeat(now=now)
        state.resolve_pending("multi_demo")
        state.set_event({
            "kind": "complete",
            "sid": "s_demo",
            "title": "Saved",
            "text": "Choices submitted",
            "ttl_ms": 5000,
        })
        yield state.build_heartbeat(now=now)
        return
    _sim_permission_pending(state, now)
    yield state.build_heartbeat(now=now)
    state.resolve_pending("req_demo")
    state.set_event({
        "kind": "complete",
        "sid": "s_demo",
        "title": "Done",
        "text": "Build finished",
        "ttl_ms": 5000,
    })
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
        state.set_event({
            "kind": "complete",
            "sid": "s_demo",
            "title": "Saved",
            "text": f"Choice {decision}",
            "ttl_ms": 5000,
        })
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
        state.set_event({
            "kind": "complete",
            "sid": "s_demo",
            "title": "Saved",
            "text": ",".join(decision),
            "ttl_ms": 5000,
        })
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
    state.set_event({
        "kind": "complete" if approved else "error",
        "sid": "s_demo",
        "title": "Done" if approved else "Denied",
        "text": "Build finished" if approved else "Request denied",
        "ttl_ms": 5000,
    })
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


def notification_prompt(payload: dict[str, Any]) -> dict[str, Any] | None:
    raw = payload.get("prompt")
    if not isinstance(raw, dict):
        return None
    pid = _clip(raw.get("id"), 40)
    kind = _clip(raw.get("kind"), 20)
    options = raw.get("options")
    if not pid or kind not in ("single_choice", "multi_choice", "notice", "free_text_required"):
        return None
    if kind in ("single_choice", "multi_choice") and (not isinstance(options, list) or not options):
        return None
    if kind in ("notice", "free_text_required") and not isinstance(options, list):
        options = []
    title = _clip(raw.get("title") or payload.get("message") or kind, 40)
    body = _clip(raw.get("body") or payload.get("message") or "", 240)
    return {
        "id": pid,
        "kind": kind,
        "title": title,
        "body": body,
        "options": options,
    }


def await_pending_decision(
    state: BridgeState,
    pid: str,
    deadline: float,
) -> Any:
    while time.time() < deadline:
        with state.lock:
            if pid in state.decisions:
                return state.decisions.pop(pid)
        time.sleep(0.05)
    return ""


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
            state.set_event({
                "kind": "complete",
                "sid": sid,
                "title": "Done",
                "text": project or "Session complete",
                "ttl_ms": 5000,
            })
        notify_state_change()
        return {}

    if event == "Notification":
        message = _clip(payload.get("message"), 120)
        prompt = notification_prompt(payload)
        if prompt:
            state.upsert_session(sid, cwd, project, branch, dirty, "waiting", model, prompt["title"], now)
            state.add_pending(prompt["id"], sid, prompt["kind"], prompt["title"], prompt["body"], prompt["options"], now)
            notify_state_change()
            if not wait_for_decision:
                return {}
            if prompt["kind"] == "notice":
                return {}
            if prompt["kind"] == "free_text_required" and not prompt["options"]:
                return {}
            decision = await_pending_decision(state, prompt["id"], time.time() + decision_timeout)
            state.resolve_pending(prompt["id"])
            notify_state_change()
            if prompt["kind"] in ("single_choice", "free_text_required") and isinstance(decision, str) and decision:
                return {"decision": decision}
            if prompt["kind"] == "multi_choice" and isinstance(decision, list) and decision:
                return {"choices": decision}
            return {}
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
        decision = await_pending_decision(state, pid, time.time() + decision_timeout)
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
    def __init__(self, state: BridgeState, on_command: Any = None) -> None:
        self.state = state
        self.on_command = on_command
        self.buf = bytearray()

    def feed(self, data: bytes) -> None:
        for b in data:
            if b in (10, 13):
                if self.buf:
                    ok = handle_device_line(self.state, bytes(self.buf))
                    if ok and self.on_command:
                        self.on_command()
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

        def _reply(self, code: int, body: bytes) -> None:
            # The client (e.g. a hook relay) may disconnect while a blocking
            # PreToolUse waits for a device decision; don't crash the request
            # thread when the socket is already gone.
            try:
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

        def do_POST(self) -> None:
            try:
                n = int(self.headers.get("Content-Length") or "0")
                payload = json.loads(self.rfile.read(n).decode("utf-8")) if n else {}
            except Exception as exc:
                self._reply(400, encode_line({"error": str(exc)}))
                return
            response = apply_hook(state, payload, on_state_change=runtime.bump.set)
            runtime.bump.set()
            self._reply(200, json.dumps(response).encode("utf-8"))

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


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
                print(f"[ble] scanning for {self.name_prefix}* ...", file=sys.stderr, flush=True)
                device = await BleakScanner.find_device_by_filter(
                    lambda d, ad: bool(d.name) and d.name.startswith(self.name_prefix),
                    timeout=10.0,
                )
                if not device:
                    print("[ble] no device found, retrying in 3s", file=sys.stderr, flush=True)
                    await asyncio.sleep(3.0)
                    continue
                print(f"[ble] connecting to {device.name} @ {device.address}", file=sys.stderr, flush=True)
                try:
                    async with BleakClient(device) as client:
                        self.client = client
                        print(f"[ble] connected {device.name} @ {device.address}", file=sys.stderr, flush=True)

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
                        print(f"[ble] disconnected {device.name}", file=sys.stderr, flush=True)
                except Exception as exc:
                    print(f"[ble] {exc!r}", file=sys.stderr, flush=True)
                    await asyncio.sleep(3.0)
                finally:
                    self.client = None

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
            state.set_event(None)
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
    runtime = BridgeRuntime(state, transport)
    reader = LineReader(state, on_command=runtime.bump.set)
    if hasattr(transport, "start"):
        transport.start(reader)
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
