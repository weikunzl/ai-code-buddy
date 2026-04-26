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
            now=40,
        )

        hb = state.build_heartbeat(now=50)
        self.assertEqual(hb["waiting"], 1)
        self.assertEqual(hb["pending"][0]["id"], "req_1")
        self.assertEqual(hb["prompt"]["id"], "req_1")
        self.assertEqual(hb["sessions"][0]["phase"], "waiting")
        self.assertEqual(hb["sessions"][0]["pending_s"], 30)

        self.assertTrue(state.handle_device_command({"cmd": "permission", "id": "req_1", "decision": "once"}))
        self.assertEqual(state.decisions["req_1"], "once")

        state.resolve_pending("req_1")
        hb = state.build_heartbeat(now=51)
        self.assertEqual(hb["pending"][0]["id"], "req_2")

    def test_resolving_one_pending_keeps_session_waiting_for_remaining_prompt(self):
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

        state.resolve_pending("req_1")
        hb = state.build_heartbeat(now=31)

        self.assertEqual(hb["pending"][0]["id"], "req_2")
        self.assertEqual(hb["sessions"][0]["phase"], "waiting")
        self.assertEqual(hb["sessions"][0]["waiting_since"], 21)
        self.assertEqual(hb["sessions"][0]["pending_s"], 10)

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
