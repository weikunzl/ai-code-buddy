# Notification Prompt Helper Milestone G Plan

## Task 1: Record The Slice

- Add ADR-0011 for the producer helper.
- Add a focused design spec for the producer-local input contract.
- Update resume notes to point at the helper milestone.

## Task 2: Implement The Helper

- Add `tools/post_notification_prompt.py`.
- Read producer-local JSON from stdin.
- Validate the bounded choice-prompt shape.
- Wrap it as `hook_event_name = "Notification"`.
- Reuse `tools/hook_relay.py` transport code.

## Task 3: Add Tests

- Add tests for:
  - valid single-choice wrapping,
  - valid multi-choice wrapping,
  - invalid producer input,
  - strict bridge failure,
  - fail-open bridge failure.

## Task 4: Docs And Verification

- Update `README.md` with helper usage.
- Update `REFERENCE.md` with the producer-local payload shape.
- Run:
  - `python3 tools/test_post_notification_prompt.py`
  - `python3 tools/test_hook_relay.py`
  - `python3 tools/test_session_bridge.py`
  - `python3 -m py_compile tools/post_notification_prompt.py tools/test_post_notification_prompt.py`
- Update `FINDINGS.md`, `HANDOFF.md`, and `PROGRESS.md`.
- Commit the doc-planning slice and implementation slice separately.
