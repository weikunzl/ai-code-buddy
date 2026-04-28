# Free-Text-Required Milestone H Plan

## Task 1: Record The Slice

- Add ADR-0012 for bounded free-text handling.
- Add a focused design spec for `notice` and `free_text_required`.
- Update resume notes to point at this milestone.

## Task 2: Bridge Support

- Extend `tools/session_bridge.py` to accept:
  - `notice`
  - `free_text_required`
- Reuse scalar `choice` answers for quick replies.
- Keep non-answering stop-and-wait prompts non-blocking.

## Task 3: Firmware Support

- Render `notice` and optionless `free_text_required` on the action screen.
- Allow `A` to send `focus`.
- Treat optioned `free_text_required` like bounded single-choice quick replies.

## Task 4: Producer Helper And Docs

- Extend `tools/post_notification_prompt.py` to allow the new kinds.
- Update `README.md` and `REFERENCE.md`.

## Task 5: Verification And Resume State

- Run:
  - `python3 tools/test_session_bridge.py`
  - `python3 tools/test_post_notification_prompt.py`
  - `pio run -e m5sticks3`
- Update `FINDINGS.md`, `HANDOFF.md`, and `PROGRESS.md`.
- Commit the doc-planning slice and implementation slice separately.
