# StickS3 Multi-Choice Prompts Milestone D Design

## Goal

Add a bounded, hardware-usable `multi_choice` prompt flow on top of the
verified BLE/USB bridge and single-choice prompt path.

## Scope

This milestone includes:

- bridge support for `choices[]`,
- simulator support for a `multi` prompt profile,
- firmware-local multi-choice selection state,
- multi-choice rendering and button handling,
- protocol documentation updates,
- hardware verification over at least one verified transport.

This milestone excludes:

- free-text prompts,
- arbitrary option counts beyond the existing `MAX_OPTIONS`,
- persisted draft selections,
- hook integration for real multi-choice producers.

## Protocol

Pending entry:

```json
{
  "id": "q_transport",
  "sid": "s_123",
  "kind": "multi_choice",
  "title": "Transport",
  "body": "pick one or more",
  "options": [
    { "id": "ble", "label": "BLE", "desc": "Wireless" },
    { "id": "usb", "label": "USB", "desc": "Serial" },
    { "id": "wifi", "label": "WiFi", "desc": "Later" }
  ]
}
```

Device answer:

```json
{"cmd":"answer","id":"q_transport","choices":["ble","usb"]}
```

Validation rules:

- `id` must match the pending item,
- `choices[]` must only contain option ids from that item,
- duplicates are rejected,
- order is preserved from the device submission.

## Firmware Design

### State

Use the existing parser/storage shape:

- `PendingDecision.selected` is the cursor index,
- `DecisionOption.selected` is the per-option toggle state.

When a new first pending item arrives:

- reset cursor to `0`,
- clear all `DecisionOption.selected` flags for that item.

### Rendering

Permission and single-choice remain unchanged.

Multi-choice view:

- title/body at the top of the action area,
- up to 4 option rows,
- current cursor row highlighted,
- each option row shows:
  - cursor marker,
  - selected/unselected marker,
  - compact label,
- footer:
  - `A: toggle`
  - `B: next`
  - `hold A: send`

### Buttons

For `multi_choice`:

- `A click`: toggle current option
- `B click`: advance cursor
- `A hold`: submit current `choices[]`

Prompt-mode long-press handling must check kind before opening the menu.

## Bridge Design

Accept:

- `{"cmd":"answer","id":"...","choices":[...]}`

Validate:

- pending id exists,
- pending kind is `multi_choice`,
- all selected ids are present in `pending.options`,
- no duplicates.

Simulator profile `multi` should:

- emit a multi-choice pending item,
- wait for returned `choices[]`,
- emit a completion event showing the selected ids.

## Verification

- `python3 tools/test_session_bridge.py`
- `python3 tools/test_session_frames.py`
- `python3 -m py_compile tools/session_bridge.py tools/test_session_frames.py`
- `pio run -e m5sticks3`
- hardware:
  - `tools/session_bridge.py --transport ble --simulate --simulate-profile multi`
  - or `--transport serial ...`
  - verify:
    - `A` toggles,
    - `B` moves cursor,
    - `A hold` submits,
    - host receives the selected ids.
