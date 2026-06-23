#!/usr/bin/env python3
import socket
import unittest
from unittest import mock

import hooks.common.ensure_bridge as ensure


class EnsureBridgeTests(unittest.TestCase):
    def test_bridge_ports_from_url(self):
        host, http, ws = ensure.bridge_ports("http://127.0.0.1:9999")
        self.assertEqual(host, "127.0.0.1")
        self.assertEqual(http, 9999)
        self.assertEqual(ws, 9877)

    def test_is_local_bridge(self):
        self.assertTrue(ensure.is_local_bridge("http://127.0.0.1:9876"))
        self.assertFalse(ensure.is_local_bridge("http://192.168.0.1:9876"))

    @mock.patch.object(ensure, "wait_for_bridge", return_value=True)
    @mock.patch.object(ensure, "start_bridge_background")
    @mock.patch.object(ensure, "bridge_is_running", side_effect=[False, False])
    @mock.patch.object(ensure, "autostart_enabled", return_value=True)
    def test_ensure_starts_when_down(self, _enabled, _running, start, _wait):
        ok = ensure.ensure_bridge_running("http://127.0.0.1:9876")
        self.assertTrue(ok)
        start.assert_called_once()

    @mock.patch.object(ensure, "start_bridge_background")
    @mock.patch.object(ensure, "bridge_is_running", return_value=True)
    def test_ensure_skips_when_running(self, _running, start):
        ok = ensure.ensure_bridge_running("http://127.0.0.1:9876")
        self.assertTrue(ok)
        start.assert_not_called()

    @mock.patch.object(ensure, "start_bridge_background")
    @mock.patch.object(ensure, "bridge_is_running", return_value=False)
    @mock.patch.object(ensure, "autostart_enabled", return_value=False)
    def test_ensure_respects_disable_flag(self, _enabled, _running, start):
        ok = ensure.ensure_bridge_running("http://127.0.0.1:9876")
        self.assertFalse(ok)
        start.assert_not_called()

    def test_port_is_open_local(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        try:
            port = sock.getsockname()[1]
            self.assertTrue(ensure.port_is_open("127.0.0.1", port))
        finally:
            sock.close()


if __name__ == "__main__":
    raise SystemExit(unittest.main())
