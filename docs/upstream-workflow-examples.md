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

## Internationalized Examples

The same host-side surfaces are now covered with checked-in UTF-8 payloads:

- Chinese hook payload:

```bash
cat docs/examples/hook-user-prompt-submit-zh.json | python3 tools/hook_relay.py
```

- Chinese `single_choice` prompt:

```bash
cat docs/examples/prompt-single-choice-zh.json | python3 tools/post_notification_prompt.py
```

- Japanese `multi_choice` prompt:

```bash
cat docs/examples/prompt-multi-choice-ja.json | python3 tools/post_notification_prompt.py
```

- Korean `free_text_required` prompt with quick replies:

```bash
cat docs/examples/prompt-free-text-required-ko.json | python3 tools/post_notification_prompt.py
```

These examples are host-side smoke coverage for the real relay/helper entry
points. They do not claim a vendor-native hook schema beyond the existing
bridge-local `Notification.prompt` contract.

## Notes

- These examples are intentionally shell-invocation based. They show the
  verified local surfaces without claiming an exact vendor hook config
  format.
- The multilingual examples above are validated by
  `python3 tools/test_workflow_examples.py`.
- For stop-and-wait host input without quick replies, change `kind` to
  `notice` or `free_text_required` without `options`.
- `tools/post_notification_prompt.py` is strict by default. Use
  `--fail-open` if bridge outages should degrade to `{}`.
