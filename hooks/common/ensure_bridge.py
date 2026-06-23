"""Ensure the local buddy bridge is running before hooks POST session events."""
from __future__ import annotations

import fcntl
import os
import pathlib
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from typing import Iterator
from urllib.parse import urlparse

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
RUNTIME_DIR = REPO_ROOT / ".buddy"
LOCK_PATH = RUNTIME_DIR / "bridge-autostart.lock"
LOG_PATH = RUNTIME_DIR / "bridge.log"


def autostart_enabled() -> bool:
    raw = os.environ.get("BUDDY_BRIDGE_AUTOSTART", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def bridge_http_url() -> str:
    from hooks.common.client import bridge_url

    return bridge_url()


def bridge_ports(url: str | None = None) -> tuple[str, int, int]:
    parsed = urlparse(url or bridge_http_url())
    host = parsed.hostname or "127.0.0.1"
    http_port = parsed.port or int(os.environ.get("BUDDY_HTTP_PORT", "9876"))
    ws_port = int(os.environ.get("BUDDY_WS_PORT", "9877"))
    return host, http_port, ws_port


def is_local_bridge(url: str | None = None) -> bool:
    host, _, _ = bridge_ports(url)
    return host in ("127.0.0.1", "localhost", "::1")


def port_is_open(host: str, port: int, timeout: float = 0.35) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def bridge_is_running(url: str | None = None) -> bool:
    host, http_port, ws_port = bridge_ports(url)
    if not port_is_open(host, http_port):
        return False
    # One process should listen on both ports; WS may bind 0.0.0.0.
    return port_is_open("127.0.0.1", ws_port) or port_is_open(host, ws_port)


@contextmanager
def _autostart_lock() -> Iterator[None]:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    with LOCK_PATH.open("a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _bridge_command(http_port: int, ws_port: int) -> list[str]:
    return [
        sys.executable,
        "-m",
        "bridge",
        "--transport",
        "websocket",
        "--http-port",
        str(http_port),
        "--ws-port",
        str(ws_port),
    ]


def start_bridge_background(url: str | None = None) -> None:
    _, http_port, ws_port = bridge_ports(url)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    log_handle = LOG_PATH.open("a", encoding="utf-8")
    env = os.environ.copy()
    pythonpath = env.get("PYTHONPATH", "")
    root = str(REPO_ROOT)
    env["PYTHONPATH"] = root if not pythonpath else f"{root}{os.pathsep}{pythonpath}"
    subprocess.Popen(
        _bridge_command(http_port, ws_port),
        cwd=str(REPO_ROOT),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )


def wait_for_bridge(
    url: str | None = None,
    *,
    timeout: float = 12.0,
    poll_interval: float = 0.25,
) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if bridge_is_running(url):
            return True
        time.sleep(poll_interval)
    return bridge_is_running(url)


def ensure_bridge_running(
    url: str | None = None,
    *,
    wait_timeout: float = 12.0,
) -> bool:
    """Start the local bridge when hooks fire and nothing is listening."""
    if not autostart_enabled():
        return bridge_is_running(url)
    target = url or bridge_http_url()
    if not is_local_bridge(target):
        return bridge_is_running(target)
    if bridge_is_running(target):
        return True
    try:
        with _autostart_lock():
            if bridge_is_running(target):
                return True
            start_bridge_background(target)
    except OSError:
        return bridge_is_running(target)
    return wait_for_bridge(target, timeout=wait_timeout)


def probe_bridge_http(url: str | None = None, timeout: float = 1.0) -> bool:
    target = url or bridge_http_url()
    req = urllib.request.Request(
        target,
        data=b'{"hook_event_name":"Notification","observe_only":true,"message":"bridge probe"}',
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except (OSError, urllib.error.URLError, TimeoutError):
        return False
