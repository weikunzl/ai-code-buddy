#!/usr/bin/env python3
import json
import threading
import unittest
import urllib.request

from bridge.core.state import BridgeState, SESSION_DONE_TTL_S
from bridge.server.http import run_http


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
        hb = state.build_heartbeat(now=11)
        self.assertNotIn("pending", hb)

    def test_prune_stale_running_session(self):
        state = BridgeState()
        state.upsert_session(
            sid="s_old",
            cwd="/tmp/repo",
            project="repo",
            branch="main",
            dirty=0,
            phase="running",
            model="codex",
            last="stale",
            now=100,
        )
        state.upsert_session(
            sid="s_live",
            cwd="/tmp/other",
            project="other",
            branch="main",
            dirty=0,
            phase="running",
            model="codex",
            last="live",
            now=2800,
        )
        hb = state.build_heartbeat(now=2801)
        self.assertEqual(hb["total"], 1)
        self.assertEqual(hb["sessions"][0]["sid"], "s_live")

    def test_prune_done_session_after_ttl(self):
        state = BridgeState()
        state.upsert_session(
            sid="s_done",
            cwd="/tmp/repo",
            project="repo",
            branch="main",
            dirty=0,
            phase="done",
            model="codex",
            last="session done",
            now=100,
        )
        hb = state.build_heartbeat(now=100 + 59)
        self.assertEqual(hb["total"], 0)
        self.assertIn("s_done", state.sessions)
        hb = state.build_heartbeat(now=100 + 61)
        self.assertEqual(hb["total"], 0)
        self.assertNotIn("s_done", state.sessions)

    def test_observe_notification_does_not_create_session(self):
        state = BridgeState()
        from bridge.core.hooks import apply_hook

        apply_hook(state, {
            "hook_event_name": "Notification",
            "observe_only": True,
            "session_id": "c1",
            "cwd": "/tmp",
            "model": "cursor",
            "message": "$ lsof -i :9877",
        }, now=100)
        hb = state.build_heartbeat(now=101)
        self.assertEqual(hb["total"], 0)
        self.assertNotIn("sessions", hb)
        self.assertNotIn("entries", hb)

    def test_observe_notification_appends_entry_when_session_active(self):
        state = BridgeState()
        from bridge.core.hooks import apply_hook

        state.upsert_session(
            "c1", "/tmp/proj", "proj", "main", 0, "running", "cursor", "working", now=50,
        )
        apply_hook(state, {
            "hook_event_name": "Notification",
            "observe_only": True,
            "session_id": "c1",
            "cwd": "/tmp/proj",
            "model": "cursor",
            "message": "$ npm test",
        }, now=100)
        hb = state.build_heartbeat(now=101)
        self.assertEqual(hb["total"], 1)
        self.assertTrue(hb["entries"][0].endswith("$ npm test"))

    def test_entries_cleared_when_no_active_sessions(self):
        state = BridgeState()
        state.upsert_session(
            "s1", "/tmp", "p", "main", 0, "running", "cursor", "hi", now=100,
        )
        state.append_entry("line", now=101)
        state.upsert_session(
            "s1", "/tmp", "p", "main", 0, "done", "cursor", "done", now=200,
        )
        hb = state.build_heartbeat(now=200 + SESSION_DONE_TTL_S + 1)
        self.assertEqual(hb["total"], 0)
        self.assertNotIn("entries", hb)


class _FakeRuntime:
    def __init__(self, state: BridgeState) -> None:
        self.state = state
        self.bump = threading.Event()

    def send_snapshot(self) -> None:
        pass


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

        def decide():
            import time
            deadline = time.time() + 3
            while time.time() < deadline and "q1" not in state.pending:
                time.sleep(0.01)
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


if __name__ == "__main__":
    unittest.main()
