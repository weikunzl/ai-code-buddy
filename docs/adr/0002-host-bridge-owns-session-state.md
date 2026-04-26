# ADR-0002: Keep Session State In A Host Bridge

Status: Accepted

Date: 2026-04-26

## Context

The firmware is resource-constrained and already has substantial local UI,
BLE, settings, stats, GIF, and power-management responsibilities. The
M5Paper reference showed that a bridge-daemon-first split works well:
hooks feed a local daemon, the daemon owns state, and firmware acts as a
small display/controller.

The CCNotify reference is useful for hook phase tracking and project
metadata, but its `cwd + branch` aggregation can collapse multiple active
sessions in the same repository.

## Decision

The host bridge owns runtime session state. It tracks sessions primarily by
Claude/Codex `session_id`, with `cwd`, project, branch, dirty count, model,
phase, latest assistant message, timing, and context metadata as attached
display fields.

The bridge owns:

- Hook ingestion.
- Session registry.
- Pending decision queue and ranking.
- Project/git metadata.
- Timing metadata.
- Long-text summarization for the small screen.
- Heartbeat rate limiting.
- Mapping device intent commands back to hook responses.

The firmware owns:

- Current local screen/page state.
- Compact JSON parsing.
- Rendering.
- Button gestures.
- Speaker tones.
- NVS-backed user preferences and local pet stats.

## Consequences

Firmware reboot should not destroy meaningful session state. The bridge can
re-send the latest snapshot after reconnect. The device remains easier to
test because it can be driven with canned JSON frames.

The first bridge should keep live state in memory. SQLite or historical
aggregation can be added later after the live loop is stable.

## Completion Criteria

- Bridge state uses `session_id` as the runtime key.
- Project and branch are display metadata, not identity.
- Pending decisions are held in a FIFO queue.
- Firmware never needs to inspect Claude/Codex internals.
