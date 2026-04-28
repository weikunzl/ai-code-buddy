# ADR-0011: Add A Notification Prompt Helper

## Status

Accepted

## Context

The repo now has:

- `tools/session_bridge.py` as the local bridge runtime,
- `tools/hook_relay.py` as the generic stdin-to-HTTP hook transport,
- a bridge-local `Notification.prompt` contract for `single_choice` and
  `multi_choice`.

What is still missing is a concrete upstream-facing producer helper for
custom workflows that want to ask the device a choice question without
building a full Claude-native hook payload by hand.

## Decision

Add a small helper under `tools/` that:

- reads a producer-local JSON payload from stdin,
- wraps it as `{"hook_event_name":"Notification", ...}`,
- reuses the relay transport path,
- prints the bridge response unchanged to stdout.

The producer-local payload omits `hook_event_name` and focuses on:

- `session_id`
- `cwd`
- `message`
- optional `model`
- `prompt`

This helper is strict by default. Invalid input or bridge failures should be
visible because the caller is explicitly asking a question and expects an
answer. Optional fail-open behavior can exist behind a flag.

## Rationale

`tools/hook_relay.py` is intentionally generic. A focused producer helper
keeps custom prompt workflows ergonomic without adding another bridge state
layer or pretending the producer payload is Claude-native.

## Consequences

- Upstream custom workflows get a concrete command they can invoke directly.
- Transport logic stays shared with the relay instead of being duplicated.
- The helper remains bounded to choice prompts; it does not open the door to
  free-text prompts, prompt history, or another prompt protocol.
