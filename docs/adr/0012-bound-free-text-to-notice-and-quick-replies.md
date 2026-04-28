# ADR-0012: Bound Free-Text To Notice And Quick Replies

## Status

Accepted

## Context

The bridge and firmware now support:

- `permission`
- `single_choice`
- `multi_choice`
- hook relay and producer helpers for bridge-local prompt payloads

The next prompt gap is free-text-required workflows. The existing design
notes already reject full arbitrary text entry on the StickS3.

The hardware constraints are unchanged:

- two buttons
- a small portrait display
- no proven keyboard UX
- no validated microphone capture path yet

## Decision

Treat free-text as a bounded stop-and-wait prompt family, not as on-device
text composition.

Add two prompt kinds:

- `notice`
- `free_text_required`

Rules:

- `notice` is informational and never expects an answer from the device
- `free_text_required` may include optional quick replies
- if quick replies are present, the device can return a scalar `choice`
- if quick replies are absent, the device can only focus the session on host

This slice does not include:

- arbitrary text entry on-device
- character-by-character cursor editing
- a keyboard UI
- microphone capture or speech-to-text

## Rationale

This keeps the product honest to the hardware.

The device can still be useful when the host needs typed input:

- show why the agent is blocked
- show the current session
- offer quick canned replies when the host provides them
- let the user focus the relevant host session

## Consequences

- Bridge validation must allow `notice` and `free_text_required`
- `single_choice` answer semantics can be reused for quick replies
- Firmware action UI must add a stop-and-wait rendering branch
- Free-text without quick replies is a non-answering state, not a broken
  empty choice prompt
