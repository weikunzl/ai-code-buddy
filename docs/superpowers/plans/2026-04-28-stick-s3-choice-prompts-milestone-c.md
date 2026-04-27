# StickS3 Single-Choice Prompts Milestone C Plan

## Task 1: Record The Slice

- Add ADR-0007 for post-USB single-choice prompt work.
- Add a formal design spec for the single-choice slice.
- Update resume notes to point at the new milestone.

## Task 2: Bridge Single-Choice Command Support

- Extend `tools/session_bridge.py` to accept:
  - `choice`
- Add simulator prompt profiles for:
  - permission
  - single-choice
- Add tests for command parsing and simulator profile selection.

## Task 3: Firmware Single-Choice State

- Keep `PendingDecision.selected` as the cursor index.
- Clear the cursor state on prompt rollover.

## Task 4: Firmware Single-Choice UI And Buttons

- Keep permission behavior unchanged.
- Preserve current single-choice flow and verify it formally.
- Confirm the current `A choose` / `B next` interaction over the simulator.

## Task 5: Docs And Verification

- Update `REFERENCE.md` for `answer` commands.
- Update `README.md` for simulator profile usage if needed.
- Run:
  - `python3 tools/test_session_bridge.py`
  - `python3 tools/test_session_frames.py`
  - `python3 -m py_compile tools/session_bridge.py tools/test_serial.py`
  - `pio run -e m5sticks3`
- Record hardware results for BLE and/or serial single-choice simulator flows when available.
