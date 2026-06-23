#!/usr/bin/env python3
import unittest
from unittest.mock import MagicMock, patch

from bridge.server.discovery import BuddyDiscovery


class DiscoveryTests(unittest.TestCase):
    @patch("bridge.server.discovery.Zeroconf")
    def test_register_service(self, mock_zc_cls):
        mock_zc = MagicMock()
        mock_zc_cls.return_value = mock_zc
        disc = BuddyDiscovery(ws_port=9877, http_port=9876, name="dev-mac")
        disc.register()
        mock_zc.register_service.assert_called_once()
        disc.unregister()


if __name__ == "__main__":
    unittest.main()
