# ADR-0009: Add Hook-Produced Choice Prompts In The Bridge

## Status

Accepted

## Context

The bridge now supports `permission`, `single_choice`, and bounded
`multi_choice` prompts end to end, and those flows are verified on hardware.

What is still missing is a real producer path. Today:

- `PreToolUse` can create a blocking `permission` prompt,
- simulator profiles can create `single_choice` and `multi_choice` prompts,
- real incoming hook payloads cannot yet create choice prompts.

The next slice should close that gap without pretending Claude has a broader
native prompt API than we actually have in this repo today.

## Decision

Add a narrow bridge-local hook contract for choice prompts.

`Notification` payloads may include a bounded `prompt` object:

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

The bridge will:

- validate the prompt shape,
- publish it as the current pending item,
- wait for a returned device answer when `wait_for_decision` is enabled,
- return a plain JSON result to the caller.

Returned results are bridge-local, not Claude-native hook output:

- single-choice: `{"decision":"usb"}`
- multi-choice: `{"choices":["ble","usb"]}`

This slice does not include:

- free-text prompts,
- nested or unbounded option payloads,
- persistent prompt history,
- a claim that Claude itself defines this prompt shape natively.

## Rationale

This keeps the integration honest and narrow.

We need a real producer path, but the current repo only owns the bridge and
device contract. A bridge-local `Notification.prompt` envelope is enough to
exercise real upstream integrations without overcommitting to an unsupported
Claude hook schema.

## Consequences

- `Notification` remains useful for plain status updates, but can now also
  carry a prompt envelope.
- The bridge becomes the authoritative waiter for choice answers, the same way
  it already owns `PreToolUse` permission waits.
- Tests and docs must clearly distinguish:
  - Claude-native `PreToolUse` permission output,
  - bridge-local choice-prompt request/response payloads.
