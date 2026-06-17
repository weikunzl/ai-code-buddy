import base64
import json
import os
import pathlib
import threading
import time
import wave
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from typing import Any

from bridge.core.util import _clip


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


@dataclass
class AudioUpload:
    aid: str
    sid: str
    decision_id: str
    cwd: str
    project: str
    sample_rate: int
    channels: int
    bits: int
    fmt: str
    started_at: int
    expected_seq: int = 0
    data: bytearray = field(default_factory=bytearray)


class BridgeState:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.sessions: OrderedDict[str, Session] = OrderedDict()
        self.pending: OrderedDict[str, Pending] = OrderedDict()
        self.decisions: dict[str, Any] = {}
        self.focused_sid: str = ""
        self.entries: deque[str] = deque(maxlen=8)
        self.event: dict[str, Any] | None = None
        self.event_set_at: float = 0.0
        self.audio_uploads: dict[str, AudioUpload] = {}

    def set_event(self, event: dict[str, Any] | None) -> None:
        # Centralise event assignment so we can expire it server-side based on
        # its own ttl_ms. Previously the bridge relied on the device sending
        # `event_dismiss` to clear `state.event`, which meant a flapping BLE
        # link could leave a stale event being re-pushed forever — the device
        # would keep treating the recurring overlay as a "new" event after its
        # own local TTL expired.
        self.event = event
        self.event_set_at = time.time() if event else 0.0

    def _event_expired(self, now: float) -> bool:
        if not self.event:
            return False
        ttl_ms = int(self.event.get("ttl_ms") or 0)
        if ttl_ms <= 0:
            return False
        return (now - self.event_set_at) * 1000.0 >= ttl_ms

    def _audio_dir_for(self, cwd: str) -> pathlib.Path:
        base = pathlib.Path(cwd) if cwd and os.path.isdir(cwd) else pathlib.Path.cwd()
        return base / ".buddy_audio"

    def _write_audio_upload(self, upload: AudioUpload, ended_at: int) -> pathlib.Path:
        out_dir = self._audio_dir_for(upload.cwd)
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(ended_at))
        suffix = f"_{upload.decision_id}" if upload.decision_id else ""
        stem = f"{stamp}_{upload.sid}{suffix}_{upload.aid}"
        wav_path = out_dir / f"{stem}.wav"
        with wave.open(str(wav_path), "wb") as wav:
            wav.setnchannels(upload.channels)
            wav.setsampwidth(max(1, upload.bits // 8))
            wav.setframerate(upload.sample_rate)
            wav.writeframes(bytes(upload.data))
        meta = {
            "id": upload.aid,
            "sid": upload.sid,
            "decision_id": upload.decision_id,
            "project": upload.project,
            "cwd": upload.cwd,
            "sample_rate": upload.sample_rate,
            "channels": upload.channels,
            "bits": upload.bits,
            "format": upload.fmt,
            "bytes": len(upload.data),
            "duration_ms": int((len(upload.data) * 1000) / max(1, upload.sample_rate * upload.channels * max(1, upload.bits // 8))),
            "saved_at": ended_at,
            "path": str(wav_path),
        }
        (out_dir / f"{stem}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
        return wav_path

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
            self.decisions.pop(pid, None)
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
            self.decisions.pop(pid, None)
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
                if pending and pending.kind in ("single_choice", "free_text_required") and choice:
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
            if cmd == "audio_begin":
                aid = str(obj.get("id") or "")
                sid = str(obj.get("sid") or "")
                fmt = str(obj.get("format") or "")
                sample_rate = int(obj.get("sample_rate") or 0)
                channels = int(obj.get("channels") or 0)
                bits = int(obj.get("bits") or 0)
                if not aid or sid not in self.sessions:
                    return False
                if fmt not in ("pcm_u8", "pcm_s16le"):
                    return False
                if sample_rate not in (8000, 11025, 16000) or channels != 1 or bits not in (8, 16):
                    return False
                sess = self.sessions[sid]
                self.audio_uploads[aid] = AudioUpload(
                    aid=aid,
                    sid=sid,
                    decision_id=_clip(obj.get("decision_id"), 40),
                    cwd=sess.cwd,
                    project=sess.project,
                    sample_rate=sample_rate,
                    channels=channels,
                    bits=bits,
                    fmt=fmt,
                    started_at=int(time.time()),
                )
                return True
            if cmd == "audio_chunk":
                aid = str(obj.get("id") or "")
                upload = self.audio_uploads.get(aid)
                if not upload:
                    return False
                seq = int(obj.get("seq") or 0)
                payload = obj.get("data")
                if seq != upload.expected_seq or not isinstance(payload, str) or not payload:
                    return False
                try:
                    chunk = base64.b64decode(payload.encode("ascii"), validate=True)
                except Exception:
                    return False
                if not chunk or len(chunk) > 2048:
                    return False
                upload.data.extend(chunk)
                upload.expected_seq += 1
                return True
            if cmd == "audio_end":
                aid = str(obj.get("id") or "")
                upload = self.audio_uploads.pop(aid, None)
                if not upload or not upload.data:
                    return False
                saved_at = int(time.time())
                path = self._write_audio_upload(upload, saved_at)
                self.entries.appendleft(f"{time.strftime('%H:%M')} note {path.name}")
                self.set_event({
                    "kind": "complete",
                    "sid": upload.sid,
                    "title": "Voice Note",
                    "text": _clip(path.name, 120),
                    "ttl_ms": 5000,
                })
                return True
            if cmd == "audio_cancel":
                aid = str(obj.get("id") or "")
                upload = self.audio_uploads.pop(aid, None)
                return upload is not None
            if cmd == "event_dismiss":
                self.set_event(None)
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
            if self._event_expired(time.time()):
                self.event = None
                self.event_set_at = 0.0
            if self.event:
                hb["event"] = self.event
            return hb
