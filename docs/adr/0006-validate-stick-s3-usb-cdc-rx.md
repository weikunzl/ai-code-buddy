# ADR-0006: Validate StickS3 USB CDC RX As A Separate Post-A Slice

Status: Accepted

Date: 2026-04-27

## Context

Milestone A proved the BLE simulator path end to end on hardware. The next
most useful transport step is native USB CDC RX on StickS3, because it
provides a simpler local debug path and reduces BLE-only coupling.

The blocker is known: current firmware skips `Serial` RX on
`BUDDY_BOARD_S3` because `Serial.available()` can report phantom bytes when
no host is attached. The ESP32 Arduino USB CDC implementation in the local
framework exposes connection state through `USBCDC::operator bool()` and
USB CDC line-state events, so USB RX can be gated on actual CDC
connectivity instead of raw `available()` alone.

## Decision

Treat StickS3 USB CDC RX as Milestone B, separate from Milestone A.

The first implementation slice should:

- enable S3 USB RX only when the CDC connection is up,
- preserve BLE as a supported transport,
- keep the firmware parser and UI transport-agnostic,
- validate the USB path with a simple host-driven JSON heartbeat flow
  before making wider transport changes.

Host bridge serial transport may be added behind a flag in the same
milestone if it stays optional and does not disturb the working BLE path.

## Consequences

This keeps the existing BLE path intact while making USB usable for direct
local debug and scripted verification. It also narrows the risk: if USB CDC
still proves flaky on some hosts, the failure stays contained to the new
milestone rather than destabilizing the already working BLE slice.

## Completion Criteria

- StickS3 firmware reads JSON heartbeats over native USB CDC only when a
  host CDC connection is active.
- No phantom-byte regressions appear when the USB host is absent.
- `pio run -e m5sticks3` still passes.
- Hardware verification shows the device reacting to USB-delivered JSON
  without BLE.
