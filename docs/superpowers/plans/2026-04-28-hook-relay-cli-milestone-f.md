# Hook Relay CLI Milestone F Plan

## Task 1: Record The Slice

- Add ADR-0010 for the relay CLI.
- Add a focused design spec for the stdin-to-HTTP forwarding path.
- Update resume notes to point at the relay milestone.

## Task 2: Implement The Relay

- Add `tools/hook_relay.py`.
- Read one JSON object from stdin.
- POST it to the local bridge HTTP endpoint.
- Print the bridge response JSON to stdout.
- Add `--bridge-url`, `--http-port`, `--timeout`, and `--strict`.

## Task 3: Add Tests

- Add a Python test script for:
  - successful forwarding,
  - invalid stdin JSON,
  - bridge-unavailable fail-open default,
  - bridge-unavailable strict failure,
  - response body pass-through.

## Task 4: Docs And Verification

- Update `README.md` with bridge start and hook relay examples.
- Update `REFERENCE.md` with the relay role.
- Run:
  - `python3 tools/test_hook_relay.py`
  - `python3 tools/test_session_bridge.py`
  - `python3 -m py_compile tools/hook_relay.py tools/test_hook_relay.py`
- Update `FINDINGS.md`, `HANDOFF.md`, and `PROGRESS.md`.
- Commit the doc-planning slice and the implementation slice separately.
