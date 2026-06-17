#!/usr/bin/env python3
import asyncio
import json
import unittest

import websockets

from bridge.core.runtime import BridgeRuntime
from bridge.core.state import BridgeState
from bridge.transports.websocket import WebSocketTransport


class WebSocketTransportTests(unittest.TestCase):
    def test_push_snapshot_and_receive_permission(self):
        state = BridgeState()
        state.upsert_session(
            sid="s_1", cwd="/tmp", project="p", branch="main", dirty=0,
            phase="waiting", model="codex", last="x", now=1,
        )
        state.add_pending("req_1", "s_1", "permission", "Bash", "ls", [], now=1)
        transport = WebSocketTransport(host="127.0.0.1", port=19877)
        runtime = BridgeRuntime(state, [transport])
        transport.start(runtime.on_device_message)
        runtime.send_snapshot()

        async def client_flow():
            async with websockets.connect("ws://127.0.0.1:19877") as ws:
                hello = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
                self.assertEqual(hello["type"], "hello")
                snap = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
                self.assertEqual(snap["type"], "snapshot")
                self.assertEqual(snap["waiting"], 1)
                await ws.send(json.dumps({"cmd": "permission", "id": "req_1", "decision": "once"}))
                await asyncio.sleep(0.2)
            self.assertEqual(state.decisions.get("req_1"), "once")

        asyncio.run(client_flow())
        transport.stop()


if __name__ == "__main__":
    unittest.main()
