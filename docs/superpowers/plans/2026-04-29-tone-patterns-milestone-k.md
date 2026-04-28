# Tone Patterns Milestone K Plan

## Task 1: Record The Slice

- Add ADR-0015 for named tone patterns before WAV assets.
- Add a focused design spec for prompt/event tone patterns.
- Update resume notes to point at this milestone.

## Task 2: Firmware Tone Refactor

- Add named tone helpers in `src/main.cpp`.
- Replace raw alert/event beep call sites with the named helpers.
- Leave general navigation/menu beeps as-is unless they overlap the alert
  paths directly.

## Task 3: Verification And Resume State

- Run `pio run -e m5sticks3`.
- Update `FINDINGS.md`, `HANDOFF.md`, and `PROGRESS.md`.
- Commit the doc-planning slice and implementation slice separately.
