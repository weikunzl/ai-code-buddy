# Stop-And-Wait Prompt Hardware Verification Design

## Goal

Verify the new `notice` and `free_text_required` prompt kinds on a connected
StickS3.

## Scope

This milestone includes:

- dedicated serial smoke profiles for:
  - `notice`
  - `free_text_required` without quick replies
  - `free_text_required` with quick replies
- firmware upload if needed
- user-observed confirmation of screen and button behavior

This milestone excludes:

- new prompt kinds,
- new bridge logic,
- BLE-specific validation.

## Expected Device Behavior

### Notice

- action screen shows title/body
- footer shows `A: focus`
- pressing `A` should send `focus`
- `B` should not deny the prompt

### Free-Text-Required Without Options

- action screen shows title/body
- footer shows `A: focus`
- pressing `A` should send `focus`

### Free-Text-Required With Options

- action screen behaves like bounded single-choice quick replies
- `A` sends the selected quick reply
- `B` cycles options

## Verification

- `pio run -e m5sticks3 -t upload`
- `python3 tools/test_serial.py --profile notice`
- `python3 tools/test_serial.py --profile free_text`
- `python3 tools/test_serial.py --profile free_text_choice`

Record the user-observed outcomes in:

- `FINDINGS.md`
- `HANDOFF.md`
- `PROGRESS.md`
