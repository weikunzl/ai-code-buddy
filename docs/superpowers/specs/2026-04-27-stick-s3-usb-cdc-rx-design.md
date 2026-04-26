# StickS3 USB CDC RX Milestone B Design

## Goal

Enable reliable JSON heartbeat RX over native USB CDC on StickS3 without
regressing the working BLE path.

## Scope

This milestone includes:

- S3 firmware USB CDC connection gating.
- USB JSON heartbeat RX through the existing `data.h` parser path.
- Simple host-side verification tooling for USB-delivered frames.

This milestone does not require:

- replacing BLE as the default verified transport,
- microphone/audio changes,
- UTF-8/CJK rendering work,
- WiFi transport,
- host persistence.

## Design

### Firmware

Keep `src/data.h` as the transport merge point. USB CDC should feed the
same `_applyJson()` path as BLE, but only when the CDC connection is
actually established.

Preferred gating order on StickS3:

1. Check USB CDC connection state (`Serial` truthiness on S3 USB CDC).
2. Only then inspect `Serial.available()`.
3. Feed the existing `_usbLine` buffer.

This keeps the parser unchanged and contains the transport behavior to the
poll layer.

### Host Verification

The existing `tools/test_serial.py` is enough as a narrow proof tool once
it can target the actual StickS3 USB modem path. A richer bridge serial
transport can remain optional.

## Verification

- Build: `pio run -e m5sticks3`
- Hardware: send compact JSON over USB CDC and confirm the device updates
  without BLE.
