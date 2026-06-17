#!/usr/bin/env python3
import argparse
import sys
import threading

from bridge.core.runtime import BridgeRuntime, LineReader
from bridge.core.snapshot import run_simulator
from bridge.core.state import BridgeState
from bridge.server.http import run_http
from bridge.transports.ble import BLETransport
from bridge.transports.serial import SerialTransport
from bridge.transports.stdout import StdoutTransport
from bridge.transports.websocket import WebSocketTransport


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--simulate", action="store_true", help="emit canned firmware frames")
    parser.add_argument("--once", action="store_true", help="emit one simulator cycle and exit")
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--http-port", type=int, default=9876)
    parser.add_argument("--ws-port", type=int, default=9877)
    parser.add_argument("--simulate-profile", choices=("permission", "single", "multi"), default="permission")
    parser.add_argument("--transport", choices=("stdout", "ble", "serial", "websocket"), default="stdout")
    parser.add_argument("--serial-port", default="", help="USB serial device path")
    parser.add_argument("--serial-baud", type=int, default=115200)
    args = parser.parse_args()
    if args.transport == "ble":
        transport = BLETransport()
    elif args.transport == "serial":
        transport = SerialTransport(port=args.serial_port, baud=args.serial_baud)
    elif args.transport == "websocket":
        transport = WebSocketTransport(port=args.ws_port)
    else:
        transport = StdoutTransport()
    if args.simulate:
        return run_simulator(args.interval, args.once, transport=transport, profile=args.simulate_profile)
    state = BridgeState()
    runtime = BridgeRuntime(state, transport)
    reader = LineReader(state, on_command=runtime.bump.set)
    if hasattr(transport, "start"):
        if getattr(transport, "accepts_dict", False):
            transport.start(runtime.on_device_message)
        else:
            transport.start(reader)
    threading.Thread(target=runtime.heartbeat_loop, daemon=True).start()
    server = run_http(state, runtime, args.http_port)
    print(f"[http] listening on 127.0.0.1:{args.http_port}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        runtime.stopped.set()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
