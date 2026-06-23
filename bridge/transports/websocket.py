import asyncio
import json
import sys
import threading
from typing import Any, Callable

BRIDGE_VERSION = "0.1.0"


class WebSocketTransport:
    accepts_dict = True

    def __init__(self, host: str = "0.0.0.0", port: int = 9877) -> None:
        self.host = host
        self.port = port
        self._clients: set[Any] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._server: Any = None
        self._on_message: Callable[[dict[str, Any]], None] | None = None
        self._ready = threading.Event()
        self._stopped = threading.Event()
        self._last_frame: dict[str, Any] | None = None

    def start(self, on_message: Callable[[dict[str, Any]], None]) -> None:
        self._on_message = on_message
        self._thread = threading.Thread(target=self._thread_main, daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=5.0):
            raise RuntimeError(f"[ws] server did not start on {self.host}:{self.port}")

    def _thread_main(self) -> None:
        try:
            import websockets
        except ImportError:
            print("[ws] install websockets to use --transport websocket", file=sys.stderr)
            return

        async def serve() -> None:
            async with websockets.serve(self._handle_client, self.host, self.port) as server:
                self._server = server
                print(f"[ws] listening on {self.host}:{self.port}", file=sys.stderr)
                self._ready.set()
                while not self._stopped.is_set():
                    await asyncio.sleep(0.1)

        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(serve())
        finally:
            self._loop.close()

    async def _handle_client(self, ws: Any) -> None:
        self._clients.add(ws)
        try:
            hello = {
                "type": "hello",
                "bridge_version": BRIDGE_VERSION,
                "token_required": False,
            }
            await ws.send(json.dumps(hello, ensure_ascii=False, separators=(",", ":")))
            if self._last_frame is not None:
                await ws.send(
                    json.dumps(self._last_frame, ensure_ascii=False, separators=(",", ":"))
                )
            async for raw in ws:
                try:
                    obj = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if not isinstance(obj, dict):
                    continue
                if obj.get("type") == "ping":
                    await ws.send(
                        json.dumps(
                            {"type": "pong", "ts": obj.get("ts")},
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )
                    )
                    continue
                if self._on_message:
                    self._on_message(obj)
        finally:
            self._clients.discard(ws)

    def write(self, obj: dict[str, Any]) -> None:
        self._last_frame = obj
        if not self._loop or not self._clients:
            return
        text = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
        asyncio.run_coroutine_threadsafe(self._broadcast(text), self._loop)

    async def _broadcast(self, text: str) -> None:
        dead: list[Any] = []
        for ws in list(self._clients):
            try:
                await ws.send(text)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._clients.discard(ws)

    def stop(self) -> None:
        self._stopped.set()
        if self._loop and self._server:
            self._loop.call_soon_threadsafe(self._server.close)
        if self._thread:
            self._thread.join(timeout=2.0)
