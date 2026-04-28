# ADR-0013: Add Runnable Upstream Workflow Examples

## Status

Accepted

## Context

The repo now has the actual runtime pieces for host integration:

- `tools/hook_relay.py`
- `tools/post_notification_prompt.py`
- bridge support for choice prompts and bounded free-text-required prompts

What is still missing is a small set of concrete, runnable examples that
show how an upstream workflow actually uses those pieces end to end.

README examples exist, but they are embedded command snippets rather than a
reusable example set that can be validated automatically.

## Decision

Add runnable upstream workflow examples as checked-in JSON payloads plus a
small smoke test.

This slice includes:

- example JSON payload files,
- a focused workflow guide under `docs/`,
- a Python smoke test that validates the example payloads against the real
  relay/helper functions.

This slice does not include:

- another runtime helper,
- another transport layer,
- vendor-specific hook config formats we cannot verify locally.

## Rationale

Checked-in example payloads are concrete, copyable, and easy to validate.
They also keep the examples aligned with the real code paths:

- hook payloads go through `tools/hook_relay.py`
- producer-local prompt payloads go through
  `tools/post_notification_prompt.py`

## Consequences

- Users get a concrete end-to-end starting point without reading bridge code.
- Example drift is reduced because payloads can be checked by tests.
- Documentation stays honest by showing shell invocation patterns rather than
  claiming an exact upstream vendor config format.
