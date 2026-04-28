# Upstream Workflow Examples Milestone I Plan

## Task 1: Record The Slice

- Add ADR-0013 for runnable upstream workflow examples.
- Add a focused design spec for example payloads plus smoke validation.
- Update resume notes to point at this milestone.

## Task 2: Add Example Payloads And Guide

- Add checked-in JSON payloads for:
  - hook relay
  - single-choice prompt helper
  - free-text-required prompt helper
- Add a focused workflow guide under `docs/`.

## Task 3: Add Smoke Test

- Add a Python test that:
  - loads the example payloads,
  - runs them through the real relay/helper entry points with fake HTTP,
  - validates the wrapped payload shapes.

## Task 4: Verification And Resume State

- Run:
  - `python3 tools/test_workflow_examples.py`
  - `python3 tools/test_hook_relay.py`
  - `python3 tools/test_post_notification_prompt.py`
  - `python3 -m py_compile tools/test_workflow_examples.py`
- Update `FINDINGS.md`, `HANDOFF.md`, and `PROGRESS.md`.
- Commit the doc-planning slice and implementation slice separately.
