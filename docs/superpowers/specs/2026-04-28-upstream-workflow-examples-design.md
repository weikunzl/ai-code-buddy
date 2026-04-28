# Upstream Workflow Examples Milestone I Design

## Goal

Add concrete, runnable upstream workflow examples for the current bridge,
relay, and notification-prompt helper.

## Scope

This milestone includes:

- checked-in example payload JSON files,
- a guide showing how to run them,
- a smoke test that validates the payloads through the real helper/relay
  functions.

This milestone excludes:

- any new bridge or firmware behavior,
- any vendor-specific configuration format claim,
- any new transport helper.

## Example Set

Add three examples:

1. `UserPromptSubmit` hook payload
2. `single_choice` producer-local prompt payload
3. `free_text_required` producer-local prompt payload

The examples should be runnable with:

```bash
cat <json> | python3 tools/hook_relay.py
cat <json> | python3 tools/post_notification_prompt.py
```

## Validation

The smoke test should verify:

- the hook payload is accepted by `hook_relay.forward_hook()`
- the prompt payloads are accepted by
  `post_notification_prompt.forward_notification_prompt()`
- the wrapped outbound payload kinds match expectations

## Documentation

Add a focused workflow guide that shows:

- start bridge
- run hook example
- run prompt example
- run free-text-required example
- expected response shape
