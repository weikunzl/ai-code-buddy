# Architecture Decision Records

These ADRs capture the agreed direction for turning the StickS3 buddy from
an approval-focused firmware reference into a compact Claude/Codex session
console.

## Current Decisions

- [ADR-0001: Build An End-To-End Milestone A Slice](0001-end-to-end-milestone-a.md)
- [ADR-0002: Keep Session State In A Host Bridge](0002-host-bridge-owns-session-state.md)
- [ADR-0003: Extend The Wire Protocol Backward-Compatibly](0003-backward-compatible-session-protocol.md)
- [ADR-0004: Keep StickS3 Firmware A Compact View Controller](0004-stick-s3-view-controller-ui.md)
- [ADR-0005: Use BLE-First Transport And Tone-First Audio](0005-ble-first-transport-tone-first-audio.md)
- [ADR-0006: Validate StickS3 USB CDC RX As A Separate Post-A Slice](0006-validate-stick-s3-usb-cdc-rx.md)
- [ADR-0007: Implement Choice Prompts After The USB Bridge Slice](0007-choice-prompts-after-usb-bridge.md)
- [ADR-0008: Treat Multi-Choice As A Separate Milestone](0008-separate-multi-choice-milestone.md)
- [ADR-0009: Add Hook-Produced Choice Prompts In The Bridge](0009-hook-produced-choice-prompts.md)
- [ADR-0010: Add A Hook Relay CLI](0010-add-a-hook-relay-cli.md)
- [ADR-0011: Add A Notification Prompt Helper](0011-add-a-notification-prompt-helper.md)
- [ADR-0012: Bound Free-Text To Notice And Quick Replies](0012-bound-free-text-to-notice-and-quick-replies.md)
- [ADR-0013: Add Runnable Upstream Workflow Examples](0013-add-runnable-upstream-workflow-examples.md)

## Implementation Plan

The detailed implementation plan for Milestone A is:

- `docs/superpowers/plans/2026-04-26-stick-s3-session-console-milestone-a.md`

The next implementation plan for post-A USB CDC RX work is:

- `docs/superpowers/plans/2026-04-27-stick-s3-usb-cdc-rx-milestone-b.md`

The next implementation plan after the verified USB bridge slice is:

- `docs/superpowers/plans/2026-04-28-stick-s3-choice-prompts-milestone-c.md`

The next implementation plan after verified single-choice is:

- `docs/superpowers/plans/2026-04-28-stick-s3-multi-choice-prompts-milestone-d.md`

The next implementation plan after verified multi-choice is:

- `docs/superpowers/plans/2026-04-28-stick-s3-hook-choice-prompts-milestone-e.md`

The next implementation plan after hook-produced choice prompts is:

- `docs/superpowers/plans/2026-04-28-hook-relay-cli-milestone-f.md`

The next implementation plan after the hook relay is:

- `docs/superpowers/plans/2026-04-28-notification-prompt-helper-milestone-g.md`

The next implementation plan after the notification prompt helper is:

- `docs/superpowers/plans/2026-04-28-free-text-required-milestone-h.md`

The next implementation plan after bounded free-text-required prompts is:

- `docs/superpowers/plans/2026-04-28-upstream-workflow-examples-milestone-i.md`

It starts with:

1. Add a minimal host bridge under `tools/`.
2. Add canned heartbeat simulation for firmware bring-up.
3. Extend `src/data.h` with sessions, pending decisions, events, and timing.
4. Add compact StickS3 action, focused-session, and session-list screens.
5. Wire button commands back to the bridge.
6. Add tone alerts for pending decisions and short-lived events.
7. Verify with `pio run -e m5sticks3` and hardware BLE tests.

## Deferred Work

The ADRs intentionally defer USB RX on StickS3, WAV sound effects, CJK font
loading, microphone recording, WiFi remote control, and persistent host
history until the end-to-end loop is proven.
