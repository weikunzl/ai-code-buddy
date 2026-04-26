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

    def _oldest_pending_since(self, sid: str) -> int:
        times = [p.pending_since for p in self.pending.values() if p.sid == sid]
        return min(times) if times else 0

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


def main() -> int:
    state = BridgeState()
    state.upsert_session("s_demo", os.getcwd(), os.path.basename(os.getcwd()), "feature/connectors", 0, "running", "codex", "bridge ready")
    sys.stdout.buffer.write(encode_line(state.build_heartbeat()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
