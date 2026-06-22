import json
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
from typing import Any

from bridge.core.hooks import apply_hook
from bridge.core.runtime import BridgeRuntime
from bridge.core.state import BridgeState
from bridge.core.util import encode_line


def run_http(state: BridgeState, runtime: BridgeRuntime, port: int, host: str = "127.0.0.1") -> HTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _reply(self, code: int, body: bytes) -> None:
            # The client (e.g. a hook relay) may disconnect while a blocking
            # PreToolUse waits for a device decision; don't crash the request
            # thread when the socket is already gone.
            try:
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

        def do_POST(self) -> None:
            try:
                n = int(self.headers.get("Content-Length") or "0")
                payload = json.loads(self.rfile.read(n).decode("utf-8")) if n else {}
            except Exception as exc:
                self._reply(400, encode_line({"error": str(exc)}))
                return
            if not isinstance(payload, dict):
                payload = {}
            wait_for_decision = payload.pop("_buddy_wait", True) is not False

            def on_change() -> None:
                runtime.bump.set()
                runtime.send_snapshot()

            response = apply_hook(
                state,
                payload,
                wait_for_decision=wait_for_decision,
                on_state_change=on_change,
            )
            on_change()
            self._reply(200, json.dumps(response).encode("utf-8"))

    return ThreadingHTTPServer((host, port), Handler)
