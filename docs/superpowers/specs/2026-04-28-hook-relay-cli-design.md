# Hook Relay CLI Milestone F Design

## Goal

Add a real hook-runner integration path for the local bridge without adding
another state machine.

## Scope

This milestone includes:

- a small CLI that reads hook JSON from stdin,
- HTTP POST forwarding to `tools/session_bridge.py`,
- stdout pass-through of the bridge response,
- safe default behavior when the bridge is absent,
- tests and docs for real hook invocation.

This milestone excludes:

- new firmware behavior,
- new bridge state semantics,
- automatic choice-prompt generation,
- free-text prompts.

## CLI Contract

Command:

```bash
python3 tools/hook_relay.py
```

Input:

- one JSON object on stdin,
- typically a Claude/Codex hook payload.

Behavior:

1. read stdin,
2. validate it is JSON,
3. POST it to `http://127.0.0.1:<port>`,
4. print the bridge response body to stdout,
5. return exit `0` on success.

Defaults:

- default port: `9876`
- default URL: `http://127.0.0.1:9876`
- default connection timeout: short, around `2s`
- bridge unavailable: print `{}` and exit `0`

Strict mode:

- `--strict` prints an error to stderr and exits non-zero if the bridge
  cannot be reached or returns invalid JSON.

## Design Constraints

- Do not duplicate `apply_hook()` logic in the relay.
- Do not reinterpret `Notification.prompt`.
- Do not invent a second waiting/decision protocol.
- Keep the relay pure Python stdlib if possible.

## Documentation

Add:

- a minimal usage example,
- a real hook-command example that pipes stdin into the relay,
- a note that bridge-local `Notification.prompt` can be produced by
  upstream custom workflows but is not required for ordinary hook relaying.

## Verification

- unit tests for stdin parsing and HTTP forwarding behavior,
- bridge-unavailable fail-open behavior,
- strict-mode failure behavior,
- `python3 -m py_compile` for the relay and its tests.
