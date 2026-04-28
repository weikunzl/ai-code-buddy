# ADR-0014: Verify Stop-And-Wait Prompts On Hardware

## Status

Accepted

## Context

`notice` and `free_text_required` are now implemented in the bridge,
producer helper, and StickS3 firmware build. What is still missing is direct
on-device verification of those new prompt kinds.

The repo already has a proven pattern for this:

- use `tools/test_serial.py` for focused USB prompt injection
- ask the connected StickS3 to render a known frame
- confirm button behavior on hardware

## Decision

Add dedicated hardware-verification profiles for:

- `notice`
- `free_text_required`

and use those profiles for the next connected-device verification slice.

This slice includes:

- serial-frame profiles,
- verification instructions,
- recorded user-observed hardware results.

This slice does not include:

- new prompt semantics,
- new transport logic,
- microphone or audio response work.

## Rationale

The protocol and build are already green. The remaining risk is user-facing:

- whether the stop-and-wait text reads correctly on-device,
- whether `A: focus` is understandable,
- whether quick-reply `free_text_required` behaves like the intended
  single-choice variant.

## Consequences

- `tools/test_serial.py` becomes the fastest way to validate these prompt
  kinds on a connected StickS3.
- Resume notes should point at the exact hardware-observed outcomes once the
  user confirms them.
