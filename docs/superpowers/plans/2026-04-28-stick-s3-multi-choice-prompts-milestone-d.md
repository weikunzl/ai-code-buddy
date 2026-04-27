# StickS3 Multi-Choice Prompts Milestone D Plan

## Task 1: Record The Slice

- Add ADR-0008 for multi-choice as a separate milestone.
- Add a formal design spec for bounded multi-choice prompts.
- Update resume notes to point at the new milestone.

## Task 2: Bridge Multi-Choice Support

- Extend `tools/session_bridge.py` to accept `choices[]`.
- Add simulator profile `multi`.
- Add tests for:
  - valid multi-choice answer,
  - duplicate rejection,
  - membership rejection,
  - simulator multi profile.

## Task 3: Firmware Multi-Choice State

- Use `DecisionOption.selected` for per-option toggles.
- Clear selection state on prompt rollover.
- Keep `PendingDecision.selected` as the cursor index.

## Task 4: Firmware Multi-Choice UI And Buttons

- Add multi-choice rendering in the action area.
- Implement:
  - `A click`: toggle
  - `B click`: next
  - `A hold`: submit
- Make prompt long-press kind-aware so menu-open does not steal submit.

## Task 5: Docs And Verification

- Update `REFERENCE.md` for `choices[]`.
- Update `README.md` if simulator usage changes.
- Run:
  - `python3 tools/test_session_bridge.py`
  - `python3 tools/test_session_frames.py`
  - `python3 -m py_compile tools/session_bridge.py tools/test_session_frames.py`
  - `pio run -e m5sticks3`
- Record hardware results for BLE or serial multi-choice simulator flow.
