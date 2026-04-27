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

    def test_running_upsert_does_not_clear_existing_pending_state(self):
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
        state.upsert_session(
            sid="s_1",
            cwd="/tmp/a",
            project="a",
            branch="main",
            dirty=0,
            phase="running",
            model="codex",
            last="still working",
            now=30,
        )

        hb = state.build_heartbeat(now=50)

        self.assertEqual(hb["waiting"], 1)
        self.assertEqual(hb["pending"][0]["id"], "req_1")
        self.assertEqual(hb["sessions"][0]["phase"], "waiting")
        self.assertEqual(hb["sessions"][0]["pending_s"], 30)

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

    def test_single_choice_answer_requires_matching_option_id(self):
        state = session_bridge.BridgeState()
        state.upsert_session("s_1", "/tmp/a", "a", "main", 0, "running", "codex", "working", now=1)
        state.add_pending(
            "q_1",
            "s_1",
            "single_choice",
            "Transport",
            "pick transport",
            [{"id": "ble", "label": "BLE"}, {"id": "usb", "label": "USB"}],
            now=2,
        )

        self.assertFalse(state.handle_device_command({"cmd": "answer", "id": "q_1", "choice": "bogus"}))
        self.assertFalse(state.handle_device_command({"cmd": "answer", "id": "missing", "choice": "usb"}))
        self.assertTrue(state.handle_device_command({"cmd": "answer", "id": "q_1", "choice": "usb"}))
        self.assertEqual(state.decisions["q_1"], "usb")

    def test_answer_command_rejects_non_choice_pending(self):
        state = session_bridge.BridgeState()
        state.upsert_session("s_1", "/tmp/a", "a", "main", 0, "running", "codex", "working", now=1)
        state.add_pending("req_1", "s_1", "permission", "Bash", "pio run", [], now=2)

        self.assertFalse(state.handle_device_command({"cmd": "answer", "id": "req_1", "choice": "usb"}))

    def test_multi_choice_answer_requires_unique_matching_option_ids(self):
        state = session_bridge.BridgeState()
        state.upsert_session("s_1", "/tmp/a", "a", "main", 0, "running", "codex", "working", now=1)
        state.add_pending(
            "m_1",
            "s_1",
            "multi_choice",
            "Transport",
            "pick one or more",
            [{"id": "ble", "label": "BLE"}, {"id": "usb", "label": "USB"}],
            now=2,
        )

        self.assertFalse(state.handle_device_command({"cmd": "answer", "id": "m_1", "choices": []}))
        self.assertFalse(state.handle_device_command({"cmd": "answer", "id": "m_1", "choices": ["ble", "ble"]}))
        self.assertFalse(state.handle_device_command({"cmd": "answer", "id": "m_1", "choices": ["bogus"]}))
        self.assertTrue(state.handle_device_command({"cmd": "answer", "id": "m_1", "choices": ["ble", "usb"]}))
        self.assertEqual(state.decisions["m_1"], ["ble", "usb"])


class SimulatorTests(unittest.TestCase):
    def test_serial_port_candidates_prefer_tty_usbmodem(self):
        def fake_glob(pattern: str):
            mapping = {
                "/dev/tty.usbmodem*": ["/dev/tty.usbmodem200"],
                "/dev/cu.usbmodem*": ["/dev/cu.usbmodem100"],
                "/dev/tty.usbserial-*": ["/dev/tty.usbserial-1"],
                "/dev/cu.usbserial-*": ["/dev/cu.usbserial-1"],
            }
            return mapping.get(pattern, [])

        self.assertEqual(
            session_bridge.serial_port_candidates(fake_glob),
            [
                "/dev/tty.usbmodem200",
                "/dev/cu.usbmodem100",
                "/dev/tty.usbserial-1",
                "/dev/cu.usbserial-1",
            ],
        )
        self.assertEqual(session_bridge.pick_serial_port("", fake_glob), "/dev/tty.usbmodem200")

    def test_simulator_frames_include_pending_and_event(self):
        frames = list(session_bridge.simulator_frames(now=100))
        self.assertGreaterEqual(len(frames), 3)
        self.assertIn("sessions", frames[0])
        self.assertIn("pending", frames[1])
        self.assertIn("event", frames[2])

    def test_single_choice_simulator_frames_include_options(self):
        frames = list(session_bridge.simulator_frames(now=100, profile="single"))
        self.assertEqual(frames[1]["pending"][0]["kind"], "single_choice")
        self.assertEqual(frames[1]["pending"][0]["options"][0]["id"], "ble")
        self.assertEqual(frames[2]["event"]["title"], "Saved")

    def test_multi_choice_simulator_frames_include_options(self):
        frames = list(session_bridge.simulator_frames(now=100, profile="multi"))
        self.assertEqual(frames[1]["pending"][0]["kind"], "multi_choice")
        self.assertEqual(frames[1]["pending"][0]["options"][1]["id"], "usb")
        self.assertEqual(frames[2]["event"]["title"], "Saved")

    def test_run_simulator_uses_supplied_transport(self):
        class FakeTransport:
            def __init__(self):
                self.started = False
                self.writes = []

            def start(self, reader):
                self.started = reader is not None

            def write(self, data):
                self.writes.append(data)

        transport = FakeTransport()
        rc = session_bridge.run_simulator(0.01, True, transport=transport)

        self.assertEqual(rc, 0)
        self.assertTrue(transport.started)
        self.assertGreaterEqual(len(transport.writes), 3)
        self.assertTrue(all(line.endswith(b"\n") for line in transport.writes))

    def test_run_single_choice_simulator_uses_supplied_transport(self):
        class FakeTransport:
            def __init__(self):
                self.started = False
                self.writes = []

            def start(self, reader):
                self.started = reader is not None

            def write(self, data):
                self.writes.append(json.loads(data.decode("utf-8")))

        transport = FakeTransport()
        rc = session_bridge.run_simulator(0.01, True, transport=transport, profile="single")

        self.assertEqual(rc, 0)
        self.assertTrue(transport.started)
        self.assertEqual(transport.writes[1]["pending"][0]["kind"], "single_choice")

    def test_run_multi_choice_simulator_uses_supplied_transport(self):
        class FakeTransport:
            def __init__(self):
                self.started = False
                self.writes = []

            def start(self, reader):
                self.started = reader is not None

            def write(self, data):
                self.writes.append(json.loads(data.decode("utf-8")))

        transport = FakeTransport()
        rc = session_bridge.run_simulator(0.01, True, transport=transport, profile="multi")

        self.assertEqual(rc, 0)
        self.assertTrue(transport.started)
        self.assertEqual(transport.writes[1]["pending"][0]["kind"], "multi_choice")

    def test_pick_serial_port_honors_explicit_value(self):
        self.assertEqual(
            session_bridge.pick_serial_port("/dev/tty.usbmodem999", lambda _pattern: []),
            "/dev/tty.usbmodem999",
        )

    def test_publish_simulator_decision_cycle_waits_for_device_decision(self):
        state = session_bridge.BridgeState()

        class InteractiveTransport:
            def __init__(self):
                self.frames = []

            def write(self, data):
                frame = json.loads(data.decode("utf-8"))
                self.frames.append(frame)
                if "pending" in frame:
                    state.decisions["req_demo"] = "once"

        transport = InteractiveTransport()
        session_bridge.publish_simulator_decision_cycle(state, transport, 0.0)

        self.assertGreaterEqual(len(transport.frames), 3)
        self.assertIn("pending", transport.frames[1])
        self.assertEqual(transport.frames[-1]["event"]["kind"], "complete")
        self.assertEqual(transport.frames[-1]["event"]["title"], "Done")

    def test_publish_single_choice_simulator_waits_for_choice(self):
        state = session_bridge.BridgeState()

        class InteractiveTransport:
            def __init__(self):
                self.frames = []

            def write(self, data):
                frame = json.loads(data.decode("utf-8"))
                self.frames.append(frame)
                if "pending" in frame:
                    state.decisions["choice_demo"] = "usb"

        transport = InteractiveTransport()
        session_bridge.publish_simulator_decision_cycle(state, transport, 0.0, profile="single")

        self.assertGreaterEqual(len(transport.frames), 3)
        self.assertEqual(transport.frames[1]["pending"][0]["kind"], "single_choice")
        self.assertEqual(transport.frames[-1]["event"]["title"], "Saved")
        self.assertEqual(transport.frames[-1]["event"]["text"], "Choice usb")

    def test_publish_multi_choice_simulator_waits_for_choices(self):
        state = session_bridge.BridgeState()

        class InteractiveTransport:
            def __init__(self):
                self.frames = []

            def write(self, data):
                frame = json.loads(data.decode("utf-8"))
                self.frames.append(frame)
                if "pending" in frame:
                    state.decisions["multi_demo"] = ["ble", "usb"]

        transport = InteractiveTransport()
        session_bridge.publish_simulator_decision_cycle(state, transport, 0.0, profile="multi")

        self.assertGreaterEqual(len(transport.frames), 3)
        self.assertEqual(transport.frames[1]["pending"][0]["kind"], "multi_choice")
        self.assertEqual(transport.frames[-1]["event"]["title"], "Saved")
        self.assertEqual(transport.frames[-1]["event"]["text"], "ble,usb")

    def test_parse_device_line_handles_json_command(self):
        state = session_bridge.BridgeState()
        state.upsert_session("s_1", "/tmp/a", "a", "main", 0, "running", "codex", "working", now=1)
        state.add_pending("req_1", "s_1", "permission", "Bash", "pio run", [], now=2)
        ok = session_bridge.handle_device_line(state, b'{"cmd":"permission","id":"req_1","decision":"deny"}\n')
        self.assertTrue(ok)
        self.assertEqual(state.decisions["req_1"], "deny")


class HookHandlingTests(unittest.TestCase):
    def test_pretool_notifies_pending_state_before_waiting_returns(self):
        state = session_bridge.BridgeState()
        snapshots = []

        def on_state_change() -> None:
            snapshots.append(state.build_heartbeat(now=25))

        response = session_bridge.apply_hook(state, {
            "hook_event_name": "PreToolUse",
            "session_id": "s_1",
            "cwd": "/tmp/project",
            "tool_name": "Bash",
            "tool_input": {"command": "pio run -e m5sticks3"},
        }, now=20, decision_timeout=0.01, on_state_change=on_state_change)

        self.assertEqual(response, {})
        self.assertGreaterEqual(len(snapshots), 1)
        self.assertIn("pending", snapshots[0])
        self.assertEqual(snapshots[0]["pending"][0]["title"], "Bash")

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
        state.add_pending("req_1", "s_1", "permission", "Bash", "pio run", [], now=20)
        session_bridge.apply_hook(state, {
            "hook_event_name": "Stop",
            "session_id": "s_1",
            "cwd": "/tmp/project",
        }, now=30)
        hb = state.build_heartbeat(now=31)
        self.assertEqual(hb["running"], 0)
        self.assertEqual(hb["waiting"], 0)
        self.assertNotIn("pending", hb)
        self.assertEqual(hb["sessions"][0]["phase"], "done")
        self.assertEqual(hb["event"]["kind"], "complete")


class TransportTests(unittest.TestCase):
    def test_chunk_bytes_splits_payload_at_requested_limit(self):
        payload = b"abcdefghijklmnopqrstuvwxyz"
        chunks = list(session_bridge.chunk_bytes(payload, 8))

        self.assertEqual(chunks, [b"abcdefgh", b"ijklmnop", b"qrstuvwx", b"yz"])
        self.assertEqual(b"".join(chunks), payload)


if __name__ == "__main__":
    unittest.main()
