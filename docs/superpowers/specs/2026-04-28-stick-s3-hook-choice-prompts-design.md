# StickS3 Hook-Produced Choice Prompts Milestone E Design

## Goal

Add a real hook-side producer path for `single_choice` and `multi_choice`
prompts without changing the verified device protocol.

## Scope

This milestone includes:

- a bridge-local `Notification.prompt` contract,
- bridge validation for bounded hook-produced choice prompts,
- blocking wait/return behavior for returned `choice` or `choices`,
- tests and protocol docs for that hook path.

This milestone excludes:

- firmware UI changes,
- free-text prompts,
- new button gestures,
- persistent prompt storage,
- any claim that this payload is part of Claude's native hook contract.

## Hook Contract

Plain status update:

```json
{
  "hook_event_name": "Notification",
  "session_id": "s_123",
  "cwd": "/repo",
  "message": "waiting for user input"
}
```

Choice prompt:

```json
{
  "hook_event_name": "Notification",
  "session_id": "s_123",
  "cwd": "/repo",
  "message": "Choose transport",
  "prompt": {
    "id": "q_transport",
    "kind": "single_choice",
    "title": "Transport",
    "body": "pick transport",
    "options": [
      { "id": "ble", "label": "BLE", "desc": "Wireless" },
      { "id": "usb", "label": "USB", "desc": "Serial" }
    ]
  }
}
```

For `multi_choice`, only `kind` changes:

```json
"kind": "multi_choice"
```

Validation rules:

- `prompt.id` is required,
- `prompt.kind` must be `single_choice` or `multi_choice`,
- `prompt.title` and `prompt.body` are clipped to the existing bridge bounds,
- `prompt.options` must be a non-empty list,
- option ids are normalized through the existing pending-option rules,
- at most 4 options are emitted to firmware.

## Bridge Behavior

For `Notification` with a valid `prompt`:

1. upsert the session in `waiting`,
2. publish a pending item using the existing pending queue,
3. notify runtime state change,
4. if `wait_for_decision` is disabled, return `{}`,
5. otherwise wait for:
   - `state.decisions[prompt.id] == "<choice>"` for `single_choice`
   - `state.decisions[prompt.id] == ["a", "b"]` for `multi_choice`
6. resolve the pending item,
7. return:
   - `{"decision":"usb"}` for `single_choice`
   - `{"choices":["ble","usb"]}` for `multi_choice`

If the prompt is invalid, treat the payload as a plain status notification.

## Protocol Stability

No firmware protocol change is required.

The pending item emitted to the device is the same shape already verified in
Milestones C and D.

## Verification

- `python3 tools/test_session_bridge.py`
- `python3 tools/test_session_frames.py`
- `python3 -m py_compile tools/session_bridge.py tools/test_session_frames.py`
- optional manual smoke by POSTing a `Notification.prompt` payload to the
  local HTTP bridge while the StickS3 is connected over BLE or USB serial.
