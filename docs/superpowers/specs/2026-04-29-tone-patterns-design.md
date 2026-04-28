# Tone Patterns Milestone K Design

## Goal

Replace scattered prompt/event `beep()` calls with named tone patterns while
staying on the current tone-first audio path.

## Scope

This milestone includes:

- named firmware helpers for alert tones,
- prompt/event call-site cleanup,
- no protocol changes.

This milestone excludes:

- WAV asset bundling,
- speaker file playback,
- microphone features.

## Target Patterns

- `input required`:
  - short attention chirp
- `approve / answer sent`:
  - short high confirm
- `deny / error`:
  - short low pattern
- `complete`:
  - two-tone rise
- `focus / stop-and-wait acknowledge`:
  - short neutral tap

Navigation/menu beeps can stay as simple one-shot cues for now.

## Files

- `src/main.cpp`
- docs and resume notes only

## Verification

- `pio run -e m5sticks3`
- optional connected-device listen test later
