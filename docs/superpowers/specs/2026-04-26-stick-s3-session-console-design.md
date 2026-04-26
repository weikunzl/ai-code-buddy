# StickS3 Session Console Milestone A Design

Date: 2026-04-26

Status: Accepted for implementation planning

Related ADRs:

- `docs/adr/0001-end-to-end-milestone-a.md`
- `docs/adr/0002-host-bridge-owns-session-state.md`
- `docs/adr/0003-backward-compatible-session-protocol.md`
- `docs/adr/0004-stick-s3-view-controller-ui.md`
- `docs/adr/0005-ble-first-transport-tone-first-audio.md`

## Goal

Build the first end-to-end Claude/Codex session-console slice for StickS3:
host hook or simulator event to local bridge, bridge state to compact JSON
over BLE, firmware parser to compact UI, and button intent back to the
bridge.

## Current Baseline

The repository is a PlatformIO firmware reference. The current firmware
already supports:

- `m5stickc-plus` and `m5sticks3` PlatformIO environments.
- BLE Nordic UART with secure pairing.
- Line-delimited JSON heartbeats.
- A legacy `prompt` approval path with `A` approve and `B` deny.
- Menus, settings, pet rendering, GIF character transfer, stats, clock, and
  StickS3 display behavior.

No host bridge for Claude/Codex hooks exists in this repository yet. The
firmware still expects simple desktop heartbeat fields and a minimal
approval prompt.

## Non-Goals

Milestone A will not include:

- WiFi remote mode.
- StickS3 microphone recording.
- On-device speech recognition or arbitrary text entry.
- WAV sound effects or OpenPeon asset conversion.
- CJK font loading.
- Host-side SQLite/history persistence.
- A full refactor of `src/main.cpp`.
- Direct code copy from GPL-licensed M5Paper reference code.

## Architecture

Milestone A uses a three-part split.

1. Claude/Codex hooks or a simulator feed a local Python bridge.
2. The bridge owns runtime session state and pushes compact JSON snapshots.
3. The StickS3 firmware acts as a view/controller and sends small commands
   back.

The host bridge is authoritative for session identity, ranking, prompt
queue order, project metadata, timing, and long-text summarization. The
firmware is authoritative only for local display state, button gestures,
speaker tones, local settings, and pet stats.

## Host Bridge Design

Create a clean implementation under `tools/`. The first bridge should be a
single executable Python 3 script with small internal classes rather than a
package. This matches the current repository's tool style while leaving
room to split modules later.

Recommended file:

- `tools/session_bridge.py`

Primary bridge responsibilities:

- Run an HTTP listener on localhost for hook JSON.
- Provide a simulator mode that emits canned session, pending-decision, and
  event snapshots without Claude/Codex hooks.
- Track sessions by `session_id`.
- Attach project, branch, dirty count, phase, model, latest short message,
  and timing metadata.
- Maintain a FIFO pending decision queue.
- Rate-limit snapshots to about 1 Hz while still sending a keepalive about
  every 10 seconds.
- Send newline-delimited JSON over BLE Nordic UART.
- Accept device commands for `permission`, `answer`, `focus`, and
  `event_dismiss`.

The bridge should keep state in memory for Milestone A. It should not create
a database or try to preserve history across restarts.

## Firmware Data Model

Extend `TamaState` in `src/data.h` with bounded fixed-size fields. Suggested
caps:

- Up to 5 session summaries.
- Up to 3 pending decisions.
- Up to 4 options per pending decision.
- Compact text buffers sized for the StickS3 screen, not full transcripts.

New firmware structs should represent:

- Session summary: `sid`, `project`, `branch`, `phase`, `model`, `last`,
  `dirty`, `elapsed_s`, `pending_s`, `focused`.
- Pending decision: `id`, `sid`, `kind`, `title`, `body`, `options[]`,
  `pending_s`, selected option index, selected mask for future multi-choice.
- Event overlay: `kind`, `sid`, `title`, `text`, `ttl_ms`, receive time,
  active flag.

Parsing rules:

- Continue parsing legacy heartbeat fields.
- Prefer `pending[0]` for the action screen.
- Fall back to legacy `prompt` if no rich pending item exists.
- Ignore unknown fields.
- Truncate all text safely.
- Increase line buffers enough for compact rich snapshots.
- Treat malformed JSON as a dropped frame, not a state reset.

## Wire Protocol

The protocol remains newline-delimited UTF-8 JSON. Existing fields stay
valid:

```json
{
  "total": 1,
  "running": 1,
  "waiting": 0,
  "msg": "editing parser",
  "entries": ["12:01 Bash done"],
  "tokens": 12000,
  "tokens_today": 12000,
  "prompt": {
    "id": "req_123",
    "tool": "Bash",
    "hint": "pio run"
  }
}
```

Milestone A may add:

```json
{
  "focused": "s_123",
  "project": "claude-desktop-buddy",
  "branch": "feature/connectors",
  "dirty": 2,
  "model": "codex",
  "assistant_msg": "Build failed in data.h parser",
  "budget": 200000,
  "sessions": [
    {
      "sid": "s_123",
      "project": "claude-desktop-buddy",
      "branch": "feature/connectors",
      "dirty": 2,
      "phase": "running",
      "model": "codex",
      "last": "editing parser",
      "elapsed_s": 540,
      "pending_s": 0,
      "focused": true
    }
  ],
  "pending": [
    {
      "id": "req_123",
      "sid": "s_123",
      "kind": "permission",
      "title": "Bash",
      "body": "pio run -e m5sticks3",
      "pending_s": 18,
      "options": []
    }
  ],
  "event": {
    "kind": "complete",
    "sid": "s_123",
    "title": "Done",
    "text": "Build finished",
    "ttl_ms": 5000
  }
}
```

Device-to-bridge commands:

```json
{"cmd":"permission","id":"req_123","decision":"once"}
{"cmd":"permission","id":"req_123","decision":"deny"}
{"cmd":"answer","id":"q_123","choice":"option_id"}
{"cmd":"focus","sid":"s_123"}
{"cmd":"event_dismiss","sid":"s_123"}
```

## StickS3 UI Design

Milestone A should add only the minimal new screens needed for the session
console.

Priority order:

1. BLE pairing passkey.
2. Pending decision action screen.
3. Short-lived event overlay.
4. Focused session screen.
5. Session list screen.
6. Existing pet/status/menu behavior.

Action screen:

- Shows the highest-priority pending decision.
- For permission decisions, `A` approves once and `B` denies.
- For single-choice decisions, `B` cycles options and `A` submits the
  current option.
- Multi-choice can be represented in parsed state but may be deferred from
  first UI wiring.

Focused session screen:

- Shows project, branch, phase, elapsed or pending time, dirty count, model,
  and latest short message.
- Uses text size no smaller than the existing `setTextSize(1)` baseline.

Session list screen:

- Shows one compact session item at a time or a short bounded list if it
  fits cleanly.
- `B` moves to the next session.
- `A` sends a focus command for the shown session.

Event overlay:

- Shows event title/text and a small countdown from `ttl_ms`.
- Does not preempt an active pending decision.
- Can be dismissed by navigation or by expiry.

Existing menus, settings, pet screens, pairing, reset, character transfer,
and status behavior should remain functional.

## Button Grammar

Milestone A uses:

- `A click`: select, confirm, approve, or focus session.
- `B click`: deny on permission, cycle options, or next page/session.
- `A hold`: existing menu behavior.
- `B hold`: reserved for future microphone recording and not required for
  core navigation.

Double-click behavior can be added if it fits cleanly, but Milestone A does
not depend on it.

## Audio

Milestone A uses tone patterns only:

- Pending decision: short attention tone.
- Approval accepted: high confirmation tone.
- Denial or error: low tone.
- Completion: short two-tone pattern.

WAV playback and OpenPeon asset conversion are deferred.

## Error Handling

Bridge:

- Invalid hook JSON returns a 400 response.
- Unknown hook events are accepted and ignored.
- Missing session ids produce displayable activity only if enough metadata
  exists.
- BLE disconnects should not clear bridge state.
- Device commands for unknown prompt ids are ignored and logged.

Firmware:

- Malformed JSON frames are ignored.
- Unknown fields are ignored.
- Missing optional fields render as blank or fallback labels.
- Stale snapshots older than about 30 seconds mark the link disconnected.
- Oversized frames are truncated by the line buffer and dropped if they do
  not parse.

## Testing And Verification

Host-side:

- Add Python tests or smoke scripts for heartbeat construction and command
  handling.
- Add a simulator mode that emits canned frames and logs device commands.

Firmware-side:

- Keep `pio run -e m5sticks3` as the required compile check.
- Use canned frames from the simulator to verify rich parser behavior.
- Hardware test BLE pairing, heartbeat display, permission approve/deny,
  focused session display, session cycling, and tones.

## Implementation Sequence

1. Build current firmware unchanged.
2. Add host bridge skeleton and simulator heartbeat mode.
3. Add bridge state model and command handling.
4. Extend firmware data structs and parsing.
5. Add action and focused-session UI.
6. Add session list/focus command behavior.
7. Add event overlay and tone alerts.
8. Verify with PlatformIO and hardware.

## Future Work

After Milestone A:

- Validate native USB CDC RX on StickS3.
- Add richer single-choice and multi-choice interaction.
- Add UTF-8-safe wrapping and later CJK subset font loading.
- Add OpenPeon-style WAV conversion and playback.
- Validate microphone support and add `B hold` recording.
- Add host-side persistence if useful.
- Explore WiFi remote mode with pairing/auth decisions.
