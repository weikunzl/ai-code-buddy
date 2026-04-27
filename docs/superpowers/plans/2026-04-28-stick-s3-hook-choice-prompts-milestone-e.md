# StickS3 Hook-Produced Choice Prompts Milestone E Plan

## Task 1: Record The Slice

- Add ADR-0009 for bridge-local hook-produced choice prompts.
- Add a focused design spec for the `Notification.prompt` contract.
- Update resume notes so future work starts from this contract.

## Task 2: Bridge Notification Prompt Handling

- Extend `tools/session_bridge.py` so `Notification` can optionally carry
  `prompt`.
- Validate:
  - `prompt.id`
  - `prompt.kind`
  - bounded `options`
- Reuse the existing pending queue and decision store.

## Task 3: Blocking Return Path

- For `single_choice`, wait for a returned scalar choice and return
  `{"decision":"..."}`.
- For `multi_choice`, wait for a returned array and return
  `{"choices":[...]}`.
- If `wait_for_decision` is false, publish the prompt and return `{}`.
- If the prompt shape is invalid, keep the current plain-notification path.

## Task 4: Tests And Docs

- Add hook tests for:
  - valid single-choice notification prompt,
  - valid multi-choice notification prompt,
  - invalid prompt fallback,
  - non-blocking publish mode.
- Update `REFERENCE.md` with the bridge-local hook contract.
- Update `README.md` with a minimal example payload.

## Task 5: Verification And Resume State

- Run:
  - `python3 tools/test_session_bridge.py`
  - `python3 tools/test_session_frames.py`
  - `python3 -m py_compile tools/session_bridge.py tools/test_session_frames.py`
- Update `FINDINGS.md`, `HANDOFF.md`, and `PROGRESS.md`.
- Commit the recorded slice and then the implementation slice separately.
