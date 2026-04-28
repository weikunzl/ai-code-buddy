#!/usr/bin/env python3
import io
import json
import unittest
import urllib.error

import hook_relay


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self.body


class HookRelayTests(unittest.TestCase):
    def test_forward_hook_passes_response_body_through(self):
        seen = {}

        def fake_urlopen(req, timeout=0):
            seen["url"] = req.full_url
            seen["body"] = req.data
            seen["timeout"] = timeout
            return _FakeResponse(b'{"decision":"usb"}')

        stdout = io.StringIO()
        stderr = io.StringIO()
        rc = hook_relay.forward_hook(
            b'{"hook_event_name":"Notification"}',
            url="http://127.0.0.1:9876",
            timeout=2.5,
            strict=False,
            stdout=stdout,
            stderr=stderr,
            urlopen=fake_urlopen,
        )

        self.assertEqual(rc, 0)
        self.assertEqual(stdout.getvalue(), '{"decision":"usb"}\n')
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(seen["url"], "http://127.0.0.1:9876")
        self.assertEqual(json.loads(seen["body"].decode("utf-8"))["hook_event_name"], "Notification")
        self.assertEqual(seen["timeout"], 2.5)

    def test_invalid_stdin_json_fails_open_by_default(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        rc = hook_relay.forward_hook(
            b"{bad",
            url="http://127.0.0.1:9876",
            timeout=2.0,
            strict=False,
            stdout=stdout,
            stderr=stderr,
        )

        self.assertEqual(rc, 0)
        self.assertEqual(stdout.getvalue(), "{}\n")
        self.assertEqual(stderr.getvalue(), "")

    def test_invalid_stdin_json_fails_in_strict_mode(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        rc = hook_relay.forward_hook(
            b"{bad",
            url="http://127.0.0.1:9876",
            timeout=2.0,
            strict=True,
            stdout=stdout,
            stderr=stderr,
        )

        self.assertEqual(rc, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("invalid stdin json", stderr.getvalue())

    def test_bridge_unavailable_fails_open_by_default(self):
        def fake_urlopen(req, timeout=0):
            raise urllib.error.URLError("connection refused")

        stdout = io.StringIO()
        stderr = io.StringIO()
        rc = hook_relay.forward_hook(
            b'{"hook_event_name":"Notification"}',
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

    def test_bridge_unavailable_fails_in_strict_mode(self):
        def fake_urlopen(req, timeout=0):
            raise urllib.error.URLError("connection refused")

        stdout = io.StringIO()
        stderr = io.StringIO()
        rc = hook_relay.forward_hook(
            b'{"hook_event_name":"Notification"}',
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

    def test_invalid_bridge_response_fails_open_by_default(self):
        def fake_urlopen(req, timeout=0):
            return _FakeResponse(b"not-json")

        stdout = io.StringIO()
        stderr = io.StringIO()
        rc = hook_relay.forward_hook(
            b'{"hook_event_name":"Notification"}',
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

    def test_main_uses_http_port_when_bridge_url_missing(self):
        seen = {}

        def fake_urlopen(req, timeout=0):
            seen["url"] = req.full_url
            return _FakeResponse(b"{}")

        stdin = io.BytesIO(b'{"hook_event_name":"Notification"}')
        stdout = io.StringIO()
        stderr = io.StringIO()

        original = hook_relay.urllib.request.urlopen
        hook_relay.urllib.request.urlopen = fake_urlopen
        try:
            rc = hook_relay.main(["--http-port", "9999"], stdin=stdin, stdout=stdout, stderr=stderr)
        finally:
            hook_relay.urllib.request.urlopen = original

        self.assertEqual(rc, 0)
        self.assertEqual(seen["url"], "http://127.0.0.1:9999")


if __name__ == "__main__":
    unittest.main()
