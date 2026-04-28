# Notification Prompt Helper Milestone G Design

## Goal

Add a concrete upstream helper for producing bridge-local choice prompts
without constructing full hook payloads manually.

## Scope

This milestone includes:

- a small helper CLI for producer-local prompt payloads,
- wrapping into `hook_event_name = "Notification"`,
- reuse of the existing relay transport,
- tests and docs for the helper.

This milestone excludes:

- new bridge behavior,
- new firmware behavior,
- free-text prompts,
- new prompt kinds beyond `single_choice` and `multi_choice`.

## Producer Input Contract

Input JSON on stdin:

```json
{
  "session_id": "s_123",
  "cwd": "/repo",
  "message": "Choose transport",
  "model": "codex",
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

Required:

- `session_id`
- `prompt.id`
- `prompt.kind`
- `prompt.options`

Accepted `prompt.kind` values:

- `single_choice`
- `multi_choice`

## Behavior

The helper will:

1. read and validate stdin JSON,
2. add `hook_event_name = "Notification"`,
3. forward the wrapped payload through the existing relay transport,
4. print the bridge response unchanged to stdout.

Defaults:

- strict by default,
- optional `--fail-open` mode for workflows that prefer `{}` on bridge
  failure.

## Reuse Rule

The helper should reuse `tools/hook_relay.py` transport code instead of
opening another raw HTTP stack with duplicate behavior.

## Verification

- tests for payload wrapping,
- tests for invalid producer input,
- tests for strict and fail-open bridge failure behavior,
- `python3 -m py_compile` for the helper and tests.
