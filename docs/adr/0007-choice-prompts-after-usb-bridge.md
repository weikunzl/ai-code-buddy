# ADR-0007: Implement Choice Prompts After The USB Bridge Slice

## Status

Accepted

## Context

Milestone A proved the session-console loop and permission prompts over BLE.
Milestone B proved the same bridge/runtime over StickS3 native USB CDC.

The next product gap is prompt richness. The current firmware and bridge can:

- show permission prompts,
- submit `once` / `deny`,
- partially render `single_choice`,
- parse `options[]`,
- send a single `choice` answer,

but they do not yet provide a complete end-to-end feature for richer
decision kinds. Multi-choice is still documentation-only, and single-choice
is not yet formally verified as a first-class prompt path.

## Decision

Treat end-to-end `single_choice` as the next post-USB milestone.

This slice includes:

- complete end-to-end `single_choice` handling,
- simulator support for permission and single-choice prompts,
- bridge command validation for `choice` answers,
- firmware button behavior and rendering verification for `single_choice`,
- protocol documentation updates.

This slice does not include:

- multi-choice submission semantics,
- free-text prompt entry,
- keyboard/text composition on-device,
- microphone capture,
- UTF-8/CJK layout work,
- host persistence changes.

## Rationale

This is the smallest next slice that materially improves the product rather
than just expanding transport/debug capability.

It also matches the current hardware constraints:

- two primary buttons,
- small portrait display,
- host bridge already authoritative for pending state,
- verified BLE and USB transports available for hardware testing.

## Consequences

- Bridge state should validate scalar `choice` answers against the option ids
  on the matching pending item instead of accepting any non-empty string.
- Firmware can keep the current `single_choice` interaction grammar:
  - `A click`: choose current option
  - `B click`: move cursor
- Simulator/test tooling becomes the primary way to verify choice UIs before
  integrating with real hook-produced prompts.
