# Stop-And-Wait Prompt Hardware Verification Milestone J Plan

## Task 1: Record The Slice

- Add ADR-0014 for hardware verification of stop-and-wait prompts.
- Add a focused verification design note.
- Update resume notes to point at this milestone.

## Task 2: Extend Serial Smoke Profiles

- Update `tools/test_serial.py` with profiles for:
  - `notice`
  - `free_text`
  - `free_text_choice`

## Task 3: Upload And Verify On Hardware

- Upload current firmware to the connected StickS3.
- Run the new serial profiles.
- Record the user-observed outcomes for:
  - `notice`
  - `free_text_required` without options
  - `free_text_required` with options

## Task 4: Resume State

- Update `FINDINGS.md`, `HANDOFF.md`, and `PROGRESS.md`.
- Commit the doc-planning slice and the verification slice separately.
