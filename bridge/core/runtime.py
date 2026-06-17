import json
import threading
import time
from typing import Any

from bridge.core.state import BridgeState
from bridge.core.util import encode_line


def handle_device_line(state: BridgeState, raw: bytes) -> bool:
    try:
        obj = json.loads(raw.decode("utf-8").strip())
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(obj, dict):
        return False
    return state.handle_device_command(obj)


class LineReader:
    def __init__(self, state: BridgeState, on_command: Any = None) -> None:
        self.state = state
        self.on_command = on_command
        self.buf = bytearray()

    def feed(self, data: bytes) -> None:
        for b in data:
            if b in (10, 13):
                if self.buf:
                    ok = handle_device_line(self.state, bytes(self.buf))
                    if ok and self.on_command:
                        self.on_command()
                    self.buf.clear()
            elif len(self.buf) < 4096:
                self.buf.append(b)


class BridgeRuntime:
    def __init__(self, state: BridgeState, transport: Any | list[Any]) -> None:
        self.state = state
        self.transports = transport if isinstance(transport, list) else [transport]
        self.bump = threading.Event()
        self.stopped = threading.Event()

    def send_snapshot(self) -> None:
        hb = self.state.build_heartbeat()
        frame = {"type": "snapshot", **hb}
        for transport in self.transports:
            if getattr(transport, "accepts_dict", False):
                transport.write(frame)
            else:
                transport.write(encode_line(hb))

    def on_device_message(self, obj: dict[str, Any]) -> None:
        if self.state.handle_device_command(obj):
            self.bump.set()

    def heartbeat_loop(self) -> None:
        last = 0.0
        while not self.stopped.is_set():
            self.bump.wait(timeout=10.0)
            self.bump.clear()
            elapsed = time.time() - last
            if elapsed < 1.0:
                time.sleep(1.0 - elapsed)
            self.send_snapshot()
            last = time.time()
