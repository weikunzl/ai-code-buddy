# ADR-0016: Validate First Embedded WAV Assets With Two Alert Cues

## Status

Accepted

## Context

Milestone K centralized prompt and event sounds behind named tone helpers in
`src/main.cpp`. That reduced drift, but the firmware still only proves
`M5.Speaker.tone()` on the StickS3.

The next audio risk is narrower than "full WAV support":

- `M5.Speaker.playWav()` needs stable in-memory asset ownership,
- source reference files are currently stereo 44.1 kHz PCM WAVs and are too
  large to bundle directly,
- replacing every alert at once would make regressions harder to isolate.

## Decision

Take the next audio slice as a constrained embedded-WAV validation milestone.

This slice includes:

- converting two short UI clips into firmware-friendly embedded assets,
- replacing only:
  - `toneInputRequired()`
  - `toneComplete()`
- keeping all other alert helpers on simple tones,
- build verification first, followed by a connected-device listen test.

This slice does not include:

- full alert-sound replacement,
- filesystem-backed sound packs,
- microphone capture,
- spoken prompts or TTS.

## Rationale

Two cues are enough to validate the real playback path:

- `input required` exercises the most common attention sound,
- `complete` exercises a second distinct cue without touching deny/error and
  focus acknowledgement paths.

Keeping the helper API unchanged lets later audio work swap individual cues
without changing prompt or event logic again.

## Consequences

- Firmware will gain a small embedded audio asset container.
- Later WAV adoption can expand helper-by-helper instead of as a single large
  rewrite.
- Any playback issues can be isolated to two known call paths instead of the
  whole alert surface.
