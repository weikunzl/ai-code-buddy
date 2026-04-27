# StickS3 Choice Prompts Milestone C Design

## Goal

Make richer prompt kinds usable on-device after the verified BLE and USB
bridge slices.

## Scope

This milestone includes:

- complete `single_choice` prompt interaction,
- simulator support for permission and single-choice prompt profiles,
- bridge support and validation for scalar `choice` answers,
- firmware rendering and button verification for `single_choice`,
- protocol documentation updates.

This milestone excludes:

- multi-choice submission semantics,
- free-text prompt entry,
- text editing controls,
- speech/audio capture,
- WiFi transport,
- persistence/schema storage beyond in-memory bridge state.

## Protocol

### Pending decisions

Existing `pending[]` entries remain the source of truth. The relevant kinds
for this milestone are:

- `permission`
- `single_choice`

Each pending entry may contain up to 4 options:

```json
{
  "id": "q_transport",
  "sid": "s_123",
  "kind": "single_choice",
  "title": "Transport",
  "body": "Pick one or more transports",
  "pending_s": 9,
  "options": [
    { "id": "ble", "label": "BLE", "desc": "Wireless" },
    { "id": "usb", "label": "USB", "desc": "Serial" }
  ]
}
```

### Device answers

Single choice:

```json
{"cmd":"answer","id":"q_transport","choice":"usb"}
```

## Firmware Design

### State model

Keep the current bounded parser shape and use
`PendingDecision.selected` as the current cursor index.

Single-choice should reset the cursor on prompt change.

### Rendering

Single-choice:

- title/body as today,
- current option shown near the bottom,
- `A: choose`, `B: next`.

### Buttons

- `single_choice`
  - `A click`: send current `choice`
  - `B click`: advance cursor

## Bridge Design

### Decisions

Bridge command handling should accept:

- `decision: "once" | "deny"` for permission,
- `choice: "<id>"` for single-choice.

Returned choices must be validated against the option ids on the matching
pending item before they are accepted.

The bridge does not need real hook integration for choice prompts in this
milestone. Simulator and protocol coverage are enough.

### Simulator

Add prompt profiles so hardware verification can explicitly exercise:

- `permission`
- `single`

## Verification

- `python3 tools/test_session_bridge.py`
- `python3 tools/test_session_frames.py`
- `python3 -m py_compile tools/session_bridge.py tools/test_serial.py`
- `pio run -e m5sticks3`
- hardware:
  - `tools/session_bridge.py --transport ble --simulate ...`
  - `tools/session_bridge.py --transport serial --simulate ...`
  - verify single-choice cursor cycle and submit.
