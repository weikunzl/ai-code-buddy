#!/usr/bin/env python3
import json
import threading
import unittest
import urllib.request

from bridge.core.state import BridgeState
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


class _FakeRuntime:
    def __init__(self, state: BridgeState) -> None:
        self.state = state
        self.bump = threading.Event()


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


if __name__ == "__main__":
    unittest.main()
