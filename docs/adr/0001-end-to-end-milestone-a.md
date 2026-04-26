# ADR-0001: Build An End-To-End Milestone A Slice

Status: Accepted

Date: 2026-04-26

## Context

The current firmware already supports BLE Nordic UART, pairing, a simple
heartbeat, approval prompts, pet rendering, menus, character transfer, and
StickS3-specific display behavior. The handoff documents recommend evolving
it into a compact Claude/Codex session console.

The main planning question was whether to start with firmware-only protocol
work, host-bridge-only work, or an end-to-end vertical slice.

## Decision

Build Milestone A as an end-to-end vertical slice:

- Claude/Codex hook or simulator event enters a local host bridge.
- The bridge owns session and pending-decision state.
- The bridge sends compact line-delimited JSON snapshots over BLE.
- The firmware parses richer optional fields.
- The StickS3 renders a minimal action/focused-session experience.
- Button actions send small intent commands back to the bridge.

## Consequences

This proves the product loop early and prevents over-designing either side
in isolation. It also means the first milestone must keep scope tight:
basic bridge, basic parser, basic screens, and tone alerts only.

Milestone A is not the place for CJK font loading, microphone recording,
WiFi remote mode, WAV effects, or host-side history persistence.

## Completion Criteria

- `pio run -e m5sticks3` succeeds.
- A bridge simulator can send session, pending decision, and event frames.
- StickS3 can show a pending permission and a focused session.
- `A` approve and `B` deny commands reach the bridge.
- BLE pairing and heartbeat display are verified on hardware.
