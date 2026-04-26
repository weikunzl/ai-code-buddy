# ADR-0004: Keep StickS3 Firmware A Compact View Controller

Status: Accepted

Date: 2026-04-26

## Context

StickS3 has a `135 x 240` screen, no touch, two primary buttons, a small
battery, BLE, speaker, and future microphone possibilities. The current
firmware centralizes UI, state machine, buttons, clock, pet rendering, and
settings in `src/main.cpp`.

The M5Paper UI is touch-first and too large for direct reuse. The StickS3
should show the next actionable item rather than a dense dashboard.

## Decision

For Milestone A, keep the firmware a compact view/controller and avoid a
large refactor. Extend existing structures and rendering helpers narrowly.

Add these minimal UI surfaces:

- Action screen for the highest-priority pending decision.
- Focused session screen with project, branch, phase, elapsed or pending
  time, model, and latest host summary.
- Session list screen showing one compact item/page at a time.
- Short-lived event overlay with countdown behavior.
- Existing idle pet/status, BLE pairing, menus, settings, reset, stats, and
  character transfer behavior remain intact.

Button behavior:

- `A click`: select, confirm, or approve.
- `B click`: next option, deny on permission prompt, or next page.
- `A hold`: menu.
- `B double-click`: cycle pending decisions or sessions when implemented.
- `B hold`: reserved for future microphone recording.

## Consequences

This keeps the first firmware change reviewable. It also avoids depending
on an untested microphone path or on text entry from a two-button device.

The code may still be centralized after Milestone A. Splitting UI modules
can be a later cleanup once the working surface area is known.

## Completion Criteria

- Font size does not go below the existing `setTextSize(1)` baseline.
- Pending decisions preempt normal session/status screens.
- Event overlays expire or dismiss back to the previous main state.
- Existing pet, pairing, settings, and character transfer flows still work.
