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
