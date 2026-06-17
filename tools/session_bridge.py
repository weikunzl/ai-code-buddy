#!/usr/bin/env python3
"""Backward-compatible entrypoint. Prefer: python -m bridge"""
from bridge.__main__ import main
from bridge.core.hooks import (
    apply_hook,
    await_pending_decision,
    git_dirty,
    git_value,
    notification_prompt,
    project_name,
    tool_body,
)
from bridge.core.runtime import BridgeRuntime, LineReader, handle_device_line
from bridge.core.snapshot import (
    publish_simulator_decision_cycle,
    run_simulator,
    seed_simulator_state,
    simulator_frames,
)
from bridge.core.state import BridgeState, Pending, Session
from bridge.core.util import chunk_bytes, encode_line
from bridge.server.http import run_http
from bridge.transports.ble import BLETransport, NUS_RX_UUID, NUS_SERVICE_UUID, NUS_TX_UUID
from bridge.transports.serial import SerialTransport, pick_serial_port, serial_port_candidates
from bridge.transports.stdout import StdoutTransport

if __name__ == "__main__":
    raise SystemExit(main())
