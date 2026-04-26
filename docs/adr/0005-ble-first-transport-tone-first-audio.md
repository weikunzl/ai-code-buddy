# ADR-0005: Use BLE-First Transport And Tone-First Audio

Status: Accepted

Date: 2026-04-26

## Context

The firmware already has BLE Nordic UART with LE Secure Connections and
encrypted characteristics. StickS3 native USB CDC RX is currently disabled
in firmware because `Serial.available()` can report phantom bytes when no
host is attached.

The StickS3 has speaker hardware and M5Unified tone/WAV APIs. OpenPeon
assets are promising for later event sounds, but they need conversion and
lifetime-safe playback from memory.

## Decision

Milestone A uses BLE as the primary verified transport. The host bridge may
include serial support behind a flag, but USB RX is not a dependency until
it is tested on StickS3 hardware.

Milestone A uses simple `M5.Speaker.tone()` patterns for audio:

- Input required or approval pending.
- Approval accepted.
- Denial or error.
- Completion.
- Resource or context warning, if included.

WAV effects, OpenPeon conversion, microphone recording, and WiFi remote
control are deferred.

## Consequences

BLE-first aligns with the current firmware's reliable path and preserves
the existing secure pairing model. Tone-first audio gives immediate
hardware feedback without adding flash/RAM asset pressure.

USB serial can still become valuable later for faster debug and larger
future microphone/audio transfers, but it should be validated separately.

## Completion Criteria

- BLE heartbeat and command round trip work on hardware.
- Tone alerts do not disrupt BLE parsing or rendering.
- USB RX remains out of the critical path for Milestone A.
- WAV and microphone work are explicitly planned as later phases.
