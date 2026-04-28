# ADR-0015: Centralize Tone Patterns Before WAV Assets

## Status

Accepted

## Context

The StickS3 firmware already emits many `beep()` calls for prompts, menu
actions, and event overlays. Tone-first audio was the original accepted
direction, but the implementation is still scattered and ad hoc.

WAV playback remains a later phase because:

- it needs asset selection and conversion,
- `M5.Speaker.playWav()` requires stable memory ownership,
- battery and speaker behavior should stay validated under simple tones first.

## Decision

Take the next audio slice as named tone patterns for prompt and event alerts.

This slice includes:

- centralizing alert tones behind named helpers,
- distinct patterns for:
  - input required
  - approval / answer sent
  - denial / error
  - completion
  - stop-and-wait focus

This slice does not include:

- WAV assets,
- `playWav()` integration,
- microphone capture,
- spoken prompts or TTS.

## Rationale

This reduces drift and makes later WAV replacement easier. Named alert
helpers also make it clearer which audible signal belongs to which user
interaction, instead of encoding semantics directly in dozens of raw
frequencies.

## Consequences

- Firmware alert code becomes easier to audit and tune.
- Later WAV work can replace tone helpers one by one without changing the
  higher-level event logic.
