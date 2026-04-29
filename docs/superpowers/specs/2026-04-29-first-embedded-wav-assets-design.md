# First Embedded WAV Assets Milestone L Design

## Goal

Validate short in-memory WAV playback on StickS3 by replacing two existing
named alert helpers with embedded assets.

## Scope

This milestone includes:

- one small firmware asset unit for embedded WAV bytes,
- converted clips for:
  - input required
  - complete
- helper-level playback changes only for those two cues,
- build verification and connected-device audio verification.

This milestone excludes:

- replacing deny/error/focus/answer-sent tones,
- runtime volume controls,
- LittleFS sound packs,
- microphone work.

## Source And Conversion Rules

Use the local OpenPeon UI sounds only as source material:

- `hover-sound.wav` for `input required`
- `confirm-sound.wav` for `complete`

Do not embed the source files directly. Convert them first to a smaller,
firmware-friendly format:

- PCM WAV
- 16-bit mono
- 22050 Hz target
- trimmed short enough for UI feedback

The checked-in firmware asset form should be static byte arrays, not runtime
file reads. Keep those arrays out of `src/main.cpp`; use a dedicated asset
unit such as `src/wav_assets.h` plus `src/wav_assets.cpp`.

## Firmware Shape

Keep the current helper boundary intact:

- `toneInputRequired()` becomes a WAV-backed helper
- `toneComplete()` becomes a WAV-backed helper
- all other named helpers remain tone-backed

The rest of the firmware should continue calling the same helper names. This
milestone is about validating the playback primitive, not redesigning audio
dispatch.

## Files

- `src/main.cpp`
- `src/wav_assets.h`
- `src/wav_assets.cpp`
- resume notes and ADR index

## Verification

Minimum verification:

- `pio run -e m5sticks3`

Connected-device verification:

- flash the connected StickS3
- trigger one prompt-arrival path
- trigger one completion-event path
- confirm both WAV cues are audible and the device remains responsive

## Risks And Limits

- Keep volume conservative; the repo notes already warn against high speaker
  volume on battery.
- Keep the implementation synchronous and small. This milestone should not
  introduce playback queues, async audio state, or mixed tone/WAV scheduling.
- If embedded assets materially bloat flash or destabilize playback, revert to
  tones for the affected cue and record that result before widening scope.
