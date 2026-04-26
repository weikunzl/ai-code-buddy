# StickS3 USB CDC RX Milestone B Plan

## Task 1: Record Milestone B Scope

- Add an ADR for post-A USB CDC RX validation.
- Add a short design spec and implementation plan.

## Task 2: Enable Safe USB CDC RX On StickS3

- Modify `src/data.h`.
- Gate S3 `Serial` RX on actual USB CDC connection state.
- Keep BLE RX unchanged.
- Verify with `pio run -e m5sticks3`.

## Task 3: Refresh USB Verification Tooling

- Update `tools/test_serial.py` so it can target the StickS3 USB modem path.
- Keep the script narrow: prove the device reacts to USB JSON.

## Task 4: Hardware Verification

- Flash current firmware.
- Run the USB test script against the connected StickS3.
- Record observed behavior in `PROGRESS.md`.
