#!/usr/bin/env python3
import io
import json
import unittest
import urllib.error

import post_notification_prompt


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self.body


class NotificationPromptHelperTests(unittest.TestCase):
    def test_build_single_choice_notification_payload(self):
        payload = post_notification_prompt.build_notification_prompt({
            "session_id": "s_1",
            "cwd": "/tmp/project",
            "message": "Choose transport",
            "model": "codex",
            "prompt": {
                "id": "q_transport",
                "kind": "single_choice",
                "title": "Transport",
                "body": "pick transport",
                "options": [{"id": "ble", "label": "BLE"}, {"id": "usb", "label": "USB"}],
            },
        })

        self.assertEqual(payload["hook_event_name"], "Notification")
        self.assertEqual(payload["session_id"], "s_1")
        self.assertEqual(payload["model"], "codex")
        self.assertEqual(payload["prompt"]["kind"], "single_choice")
        self.assertEqual(payload["prompt"]["options"][1]["id"], "usb")

    def test_build_multi_choice_payload_defaults_message_and_cwd(self):
        payload = post_notification_prompt.build_notification_prompt({
            "session_id": "s_1",
            "prompt": {
                "id": "q_transport",
                "kind": "multi_choice",
                "title": "Transport",
                "options": [{"id": "ble", "label": "BLE"}],
            },
        }, cwd_default="/tmp/default")

        self.assertEqual(payload["cwd"], "/tmp/default")
        self.assertEqual(payload["message"], "Transport")
        self.assertEqual(payload["prompt"]["body"], "Transport")
        self.assertEqual(payload["prompt"]["kind"], "multi_choice")

    def test_invalid_producer_payload_returns_error(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        rc = post_notification_prompt.forward_notification_prompt(
            b'{"session_id":"s_1","prompt":{"kind":"single_choice"}}',
            url="http://127.0.0.1:9876",
            timeout=2.0,
            strict=True,
            stdout=stdout,
            stderr=stderr,
        )

        self.assertEqual(rc, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("invalid prompt payload", stderr.getvalue())

    def test_strict_bridge_failure_is_nonzero(self):
        def fake_urlopen(req, timeout=0):
            raise urllib.error.URLError("connection refused")

        stdout = io.StringIO()
        stderr = io.StringIO()
        rc = post_notification_prompt.forward_notification_prompt(
            b'{"session_id":"s_1","prompt":{"id":"q_transport","kind":"single_choice","options":[{"id":"ble","label":"BLE"}]}}',
            url="http://127.0.0.1:9876",
            timeout=2.0,
            strict=True,
            stdout=stdout,
            stderr=stderr,
            urlopen=fake_urlopen,
        )

        self.assertEqual(rc, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("bridge unavailable", stderr.getvalue())

    def test_fail_open_bridge_failure_returns_empty_object(self):
        def fake_urlopen(req, timeout=0):
            raise urllib.error.URLError("connection refused")

        stdout = io.StringIO()
        stderr = io.StringIO()
        rc = post_notification_prompt.forward_notification_prompt(
            b'{"session_id":"s_1","prompt":{"id":"q_transport","kind":"single_choice","options":[{"id":"ble","label":"BLE"}]}}',
            url="http://127.0.0.1:9876",
            timeout=2.0,
            strict=False,
            stdout=stdout,
            stderr=stderr,
            urlopen=fake_urlopen,
        )

        self.assertEqual(rc, 0)
        self.assertEqual(stdout.getvalue(), "{}\n")
        self.assertEqual(stderr.getvalue(), "")

    def test_forward_passes_wrapped_notification_to_relay(self):
        seen = {}

        def fake_urlopen(req, timeout=0):
            seen["payload"] = json.loads(req.data.decode("utf-8"))
            return _FakeResponse(b'{"decision":"usb"}')

        stdout = io.StringIO()
        stderr = io.StringIO()
        rc = post_notification_prompt.forward_notification_prompt(
            b'{"session_id":"s_1","cwd":"/tmp/project","message":"Choose transport","prompt":{"id":"q_transport","kind":"single_choice","options":[{"id":"ble","label":"BLE"},{"id":"usb","label":"USB"}]}}',
            url="http://127.0.0.1:9876",
            timeout=2.0,
            strict=True,
            stdout=stdout,
            stderr=stderr,
            urlopen=fake_urlopen,
        )

        self.assertEqual(rc, 0)
        self.assertEqual(stdout.getvalue(), '{"decision":"usb"}\n')
        self.assertEqual(seen["payload"]["hook_event_name"], "Notification")
        self.assertEqual(seen["payload"]["prompt"]["id"], "q_transport")

    def test_main_uses_longer_default_timeout(self):
        seen = {}

        def fake_urlopen(req, timeout=0):
            seen["timeout"] = timeout
            return _FakeResponse(b"{}")

        original = post_notification_prompt.hook_relay.urllib.request.urlopen
        post_notification_prompt.hook_relay.urllib.request.urlopen = fake_urlopen
        try:
            rc = post_notification_prompt.main(
                [],
                stdin=io.BytesIO(
                    b'{"session_id":"s_1","prompt":{"id":"q_transport","kind":"single_choice","options":[{"id":"ble","label":"BLE"}]}}'
                ),
                stdout=io.StringIO(),
                stderr=io.StringIO(),
            )
        finally:
            post_notification_prompt.hook_relay.urllib.request.urlopen = original

        self.assertEqual(rc, 0)
        self.assertEqual(seen["timeout"], 35.0)


if __name__ == "__main__":
    unittest.main()
