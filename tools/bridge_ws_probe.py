#!/usr/bin/env python3
"""Print LAN URLs and probe the local buddy bridge WebSocket."""
from __future__ import annotations

import asyncio
import json
import socket
import sys


def lan_ips() -> list[str]:
    ips: list[str] = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ips.append(s.getsockname()[0])
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except OSError:
        pass
    return ips


async def probe(url: str) -> None:
    try:
        import websockets
    except ImportError:
        print("pip install websockets", file=sys.stderr)
        raise SystemExit(1)
    try:
        async with websockets.connect(url, open_timeout=3) as ws:
            raw = await asyncio.wait_for(ws.recv(), timeout=3)
            hello = json.loads(raw)
            print(f"OK {url} -> {hello}")
    except Exception as exc:
        print(f"FAIL {url} -> {exc}")


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9877
    ips = lan_ips() or ["127.0.0.1"]
    print("Suggested phone URLs:")
    for ip in ips:
        print(f"  ws://{ip}:{port}")
    print(f"\nProbing ws://127.0.0.1:{port} (bridge must be running)…")
    asyncio.run(probe(f"ws://127.0.0.1:{port}"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
