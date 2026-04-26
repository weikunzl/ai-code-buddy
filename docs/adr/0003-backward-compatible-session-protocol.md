# ADR-0003: Extend The Wire Protocol Backward-Compatibly

Status: Accepted

Date: 2026-04-26

## Context

`REFERENCE.md` defines the current maker-facing BLE protocol. The existing
desktop heartbeat contains simple counts, transcript entries, token counts,
and a legacy `prompt` object with `id`, `tool`, and `hint`.

Milestone A needs richer multi-session state, pending decisions beyond a
single approval prompt, timing metadata, and short-lived events. Existing
firmware behavior must remain compatible with old heartbeat frames.

## Decision

Grow the existing newline-delimited JSON protocol with optional fields.
Unknown fields remain ignorable.

The bridge should continue sending legacy fields:

- `total`
- `running`
- `waiting`
- `msg`
- `entries`
- `tokens`
- `tokens_today`
- `prompt`

The bridge may also send:

- `focused`
- `project`
- `branch`
- `dirty`
- `model`
- `assistant_msg`
- `budget`
- `sessions[]`
- `pending[]`
- `event`

Session summaries should be compact and bounded. Pending decisions should
include a short `id`, `sid`, `kind`, `title`, optional `body`, optional
`options[]`, and timing fields such as `pending_s`.

Firmware should prefer `pending[0]` for the new action screen, then fall
back to legacy `prompt` if no richer pending item exists.

## Consequences

The existing Claude Desktop hardware-buddy flow can keep working. The new
bridge can provide richer state without requiring a protocol reset.

Large text must be summarized or capped by the host before it reaches the
StickS3. The firmware line buffer should grow enough for compact snapshots,
but the protocol should not rely on sending long transcripts.

## Completion Criteria

- Existing simple heartbeat frames still parse.
- Legacy `prompt` approval still works.
- Rich `sessions[]`, `pending[]`, and `event` frames parse safely.
- Firmware ignores fields it does not understand.
- One frame remains small enough for reliable BLE line transport.
