# Free-Text-Required Milestone H Design

## Goal

Support bounded free-text-required workflows on the StickS3 without adding
an on-device keyboard.

## Scope

This milestone includes:

- bridge support for `notice` and `free_text_required`
- optional quick replies on `free_text_required`
- firmware action rendering for stop-and-wait prompts
- focus-session action from the prompt screen
- tests and docs

This milestone excludes:

- arbitrary text entry
- text composition UI
- microphone capture
- speech-to-text

## Protocol

Pending notice:

```json
{
  "id": "n_followup",
  "sid": "s_123",
  "kind": "notice",
  "title": "Need host input",
  "body": "Type the answer on your computer"
}
```

Pending free-text-required without quick replies:

```json
{
  "id": "q_followup",
  "sid": "s_123",
  "kind": "free_text_required",
  "title": "Need details",
  "body": "Type the path on your computer"
}
```

Pending free-text-required with quick replies:

```json
{
  "id": "q_followup",
  "sid": "s_123",
  "kind": "free_text_required",
  "title": "Confirm target",
  "body": "Pick a preset or type on host",
  "options": [
    { "id": "here", "label": "Here", "desc": "Use current repo" },
    { "id": "tmp", "label": "Tmp", "desc": "Use /tmp" }
  ]
}
```

Response rules:

- `notice`: no device answer
- `free_text_required` without options: no device answer
- `free_text_required` with options: device may return
  `{"cmd":"answer","id":"q_followup","choice":"here"}`

## Bridge Behavior

Validation:

- accepted kinds:
  - `permission`
  - `single_choice`
  - `multi_choice`
  - `notice`
  - `free_text_required`
- `single_choice` and `multi_choice` still require non-empty `options`
- `notice` and `free_text_required` may omit `options`

Apply-hook behavior:

- `notice`: publish pending and return `{}`
- `free_text_required` without options: publish pending and return `{}`
- `free_text_required` with options:
  - publish pending
  - when waiting is enabled, wait for a scalar `choice`
  - return `{"decision":"..."}` on success

## Firmware Behavior

Action screen:

- `notice` / `free_text_required` without options:
  - show title/body
  - footer `A: focus`
  - no deny/submit action
- `free_text_required` with options:
  - render like bounded single-choice quick replies
  - `A: send`
  - `B: next`

Buttons:

- `A click` on `notice` or optionless `free_text_required`: send `focus`
- `A click` on optioned `free_text_required`: send `answer.choice`
- `B click` on optioned `free_text_required`: next quick reply

## Verification

- `python3 tools/test_session_bridge.py`
- `python3 tools/test_post_notification_prompt.py`
- `pio run -e m5sticks3`
- optional manual smoke using `tools/post_notification_prompt.py`
