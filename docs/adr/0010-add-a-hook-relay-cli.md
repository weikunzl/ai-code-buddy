# ADR-0010: Add A Hook Relay CLI

## Status

Accepted

## Context

The bridge now exposes a local HTTP endpoint and can handle:

- plain hook status events,
- blocking `PreToolUse` permission prompts,
- bridge-local `Notification.prompt` choice prompts.

What is still missing is the narrow transport layer from a real hook runner
to that bridge. Right now the repo has:

- `tools/session_bridge.py` as the bridge daemon,
- manual `curl` examples,
- simulator profiles.

It does not yet have a small CLI that a real Claude/Codex hook command can
invoke directly.

## Decision

Add a tiny hook relay CLI under `tools/` that:

- reads one JSON object from stdin,
- POSTs it to the local bridge HTTP endpoint,
- prints the bridge response JSON to stdout,
- exits successfully with `{}` when the bridge is unreachable unless strict
  mode is requested.

This relay is intentionally transport-only. It does not:

- own any session or prompt state,
- transform hook semantics,
- generate device protocol directly,
- duplicate `apply_hook()` logic outside the bridge.

## Rationale

The bridge already owns the correct wait/answer behavior. Adding another
adapter state machine would create drift and make real hook behavior harder
to reason about.

The smallest useful upstream integration is therefore:

- hook runner -> relay CLI -> local bridge HTTP endpoint.

That path supports both existing `PreToolUse` permissions and the new
bridge-local `Notification.prompt` flow.

## Consequences

- Real hook setup can use a single stable local command.
- The relay can fail open by default so a missing bridge does not break a
  user's editor/terminal workflow.
- Documentation must show example hook configuration and explicitly note
  that bridge-local `Notification.prompt` is optional, not Claude-native.
