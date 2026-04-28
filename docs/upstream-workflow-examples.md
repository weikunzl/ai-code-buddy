# Upstream Workflow Examples

These examples are the concrete entry points for the current host-side
integration surface:

- hook payloads go through `tools/hook_relay.py`
- producer-local prompt payloads go through
  `tools/post_notification_prompt.py`

Start the bridge first:

```bash
python3 tools/session_bridge.py --transport serial --serial-port /dev/tty.usbmodem...
```

## Example 1: Hook Relay

Replay a `UserPromptSubmit` hook payload:

```bash
cat docs/examples/hook-user-prompt-submit.json | python3 tools/hook_relay.py
```

Expected response:

```json
{}
```

## Example 2: Choice Prompt

Ask the device a `single_choice` question:

```bash
cat docs/examples/prompt-single-choice.json | python3 tools/post_notification_prompt.py
```

Expected response after the device answers:

```json
{"decision":"usb"}
```

## Example 3: Free-Text-Required With Quick Replies

Ask the device for a bounded quick reply while the real typed response still
belongs on the host:

```bash
cat docs/examples/prompt-free-text-required.json | python3 tools/post_notification_prompt.py
```

Expected response after the device answers:

```json
{"decision":"here"}
```

## Notes

- These examples are intentionally shell-invocation based. They show the
  verified local surfaces without claiming an exact vendor hook config
  format.
- For stop-and-wait host input without quick replies, change `kind` to
  `notice` or `free_text_required` without `options`.
- `tools/post_notification_prompt.py` is strict by default. Use
  `--fail-open` if bridge outages should degrade to `{}`.
