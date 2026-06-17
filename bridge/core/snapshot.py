import json
import os
import sys
import time
from typing import Any

from bridge.core.hooks import git_dirty, git_value
from bridge.core.runtime import LineReader
from bridge.core.state import BridgeState
from bridge.core.util import encode_line
from bridge.transports.stdout import StdoutTransport


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
