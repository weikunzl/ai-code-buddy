# StickS3 Session Console Design

Last updated: 2026-04-26

This document records the current design direction for evolving the
StickS3 firmware from a simple Claude approval buddy into a compact
Claude/Codex session console.

The central constraint is the StickS3 itself: `135 x 240`, no touch, two
main buttons, small battery, BLE/USB transport, speaker available, and
microphone support planned later. The device should show the next most
actionable thing, not copy the touch-first M5Paper dashboard.

## Goals

- Display Claude/Codex sessions at different levels of detail.
- Remove tight "force bindings" to Claude Desktop approval-only behavior.
- Support multiple sessions and projects.
- Show pending decisions beyond approve/deny, including single-choice,
  multi-choice, free-text-required notices, and stop-and-wait states.
- Play sounds for important events such as input required, completion,
  error, approval, and denial.
- Reserve an interaction path for later microphone recording.
- Keep firmware as a compact view/controller; host bridge owns session
  state, project aggregation, ranking, audio file processing, and agent
  integration.

## Non-Goals For The First Build

- Do not implement full arbitrary text entry on the StickS3.
- Do not make firmware a session database.
- Do not clone the M5Paper layout.
- Do not add WiFi remote mode before BLE/USB bridge behavior is stable.
- Do not implement on-device speech-to-text. Later microphone recordings
  should be sent to the host, transcribed there, and then passed to Claude,
  Codex, or another coding agent.

## Display Principles

- Minimum accepted text size is the current smallest firmware font:
  built-in `setTextSize(1)`.
- Avoid shrinking below that size to fit more data.
- Prefer one meaningful object per screen.
- Use pages and countdown-driven temporary overlays instead of dense
  dashboards.
- Host should pre-rank and pre-summarize state so firmware does not need
  to reason over long transcripts.
- Long text should be summarized by the host and, when needed, split into
  pages.
- UI state should return to the previous main state after temporary event
  overlays expire.

## Chinese/CJK Font Direction

M5Paper Buddy uses `/cjk.ttf` in LittleFS and loads it into the canvas with
glyph render caches. It also uses codepoint-aware width estimation and
wrapping because naive byte slicing can split UTF-8 and crash rendering.

For StickS3, Chinese/CJK support is desirable, but it must be treated as a
separate implementation slice:

- The M5Paper font file is about 3.4 MB.
- StickS3 has 8 MB flash and the current partition layout has about 3.8 MB
  filesystem space, so the full font may technically fit but leaves little
  room for GIF characters, sound packs, and future assets.
- A subsetted CJK font is preferred for practical builds.
- Firmware text wrapping must be UTF-8/codepoint-aware before rendering
  user text.
- If CJK font loading fails, the device should fall back gracefully rather
  than crash.
- The host can optionally provide ASCII or pinyin/English summaries until
  CJK rendering is ready.

Recommended CJK path:

1. Keep English/ASCII UI labels for the first session-console milestone.
2. Add UTF-8-safe truncation/wrapping before accepting arbitrary user text.
3. Test loading a small/subsetted CJK font from LittleFS on StickS3.
4. Add a language/display setting after font rendering is stable.
5. Only consider the full M5Paper font if storage pressure is acceptable.

## Host And Firmware Split

The host bridge should own:

- Claude/Codex hook ingestion.
- Session registry keyed by session id.
- Project, branch, dirty-state, model, phase, and context metadata.
- Session and decision timing metadata.
- Pending decision queue and priority ranking.
- Long-text summarization for small display use.
- Completion/error/input-required countdown policy.
- Audio recording ingestion, transcription, and forwarding to agents.
- Audio asset conversion or audio file generation when needed.

The firmware should own:

- Current screen/page state.
- Compact JSON parsing.
- Rendering.
- Button gestures.
- Speaker playback.
- Local settings and stats in NVS.
- Sending user intents back to the host.

## Priority Strategy

The host should send ranked state. The firmware should render by priority:

1. Blocking decision requiring user input.
2. Microphone recording state, when later implemented.
3. Short-lived completion/error/input-required event overlay.
4. Focused running session or project.
5. Other waiting sessions/projects.
6. Idle buddy/status screen.

When multiple decisions are pending, firmware shows the highest-priority
decision first. The user can cycle pending items, but the host remains the
source of ranking.

## Timing Metadata

The host should include timestamps and/or precomputed ages so the StickS3
can show elapsed time and pending time. This gives the user useful context
without making the firmware infer session history.

Recommended fields:

- `started_at`: Unix epoch seconds when a session/task started.
- `updated_at`: Unix epoch seconds for the latest meaningful activity.
- `waiting_since`: Unix epoch seconds when a session entered a blocked or
  waiting state.
- `pending_since`: Unix epoch seconds when a decision became actionable.
- `elapsed_s`: optional host-computed elapsed seconds.
- `pending_s`: optional host-computed pending/waiting seconds.
- `deadline_at`: optional Unix epoch seconds for time-sensitive decisions.

Use both absolute timestamps and optional computed durations when practical:

- Absolute timestamps survive reconnects and let firmware recompute display
  ages after receiving time sync.
- Computed durations are useful when time sync is unavailable or unreliable.
- Firmware should prefer local recomputation from timestamps after time sync,
  and fall back to `elapsed_s` / `pending_s`.
- Host ranking remains authoritative; firmware displays timing as context,
  not as the main priority algorithm.

Display guidance:

- Focused session: show elapsed runtime, for example `run 12m`.
- Pending decision: show pending age, for example `wait 2m14s`.
- Session list: show compact age markers like `3m`, `1h`, or `now`.
- Event overlay: show countdown from `ttl_ms`, not session elapsed time.
- Stale link: if heartbeat is older than about 30 seconds, mark state stale.

## Countdown Logic

Temporary events should include countdown metadata from the host:

```json
{
  "event": {
    "kind": "complete",
    "sid": "s_123",
    "title": "Done",
    "text": "Tests finished",
    "ttl_ms": 5000
  }
}
```

Firmware behavior:

- Show the event overlay immediately if no higher-priority decision is
  active.
- Display a small countdown/progress indicator.
- If the event expires, return to the previous main state, such as focused
  project or project list.
- If a decision arrives during the countdown, preempt the event.
- If the user presses a navigation button, allow early dismissal and return
  to main state.

Suggested defaults:

- Completion: 4-6 seconds.
- Error: 8-12 seconds or until dismissed, depending severity.
- Input required: no expiry while still blocking.
- Approval/answer sent: 1.5-2 seconds confirmation, then return.

## Button Grammar

StickS3 has two main buttons, and each can provide single click, double
click, and hold. That gives six gestures. We should reserve one clear
gesture for future microphone recording.

Suggested global grammar:

| Gesture | Default Meaning |
| --- | --- |
| A click | Select, confirm, open focused item |
| B click | Next item, next option, next page |
| A double-click | Back to main/focused session |
| B double-click | Cycle pending decisions or projects |
| A hold | Open menu / submit multi-select where applicable |
| B hold | Reserved for microphone record later |

Microphone reservation:

- `B hold` should become press-and-hold-to-record later.
- Recording should start after a threshold such as 600-800 ms.
- Releasing `B` should stop recording and send/upload the file to the host.
- If the current screen is a decision, the recording should attach as
  extra feedback to that decision.
- If no decision is active, the recording should attach to the focused
  session/project.

Because `B hold` is reserved, avoid making it essential for core
navigation. It can temporarily be used for defer/cancel only if that can be
remapped cleanly once microphone support lands.

## Decision Interaction

### Permission Prompt

- `A click`: approve once.
- `B click`: deny.
- `B double-click`: next pending prompt if there are multiple.
- `A double-click`: return to main without answering.
- `A hold`: details/menu.
- `B hold`: reserved for future voice note attachment.

### Single-Choice Question

- Show project/session, question title, and current option.
- `B click`: cycle option.
- `A click`: submit current option.
- `B double-click`: next pending decision.
- `A hold`: show details/description page.
- `B hold`: later voice note attachment.

### Multi-Choice Question

- Show one option at a time with selected/unselected marker.
- `A click`: toggle current option.
- `B click`: next option.
- `A hold`: submit selected options.
- `A double-click`: back/cancel selection changes.
- `B hold`: later voice note attachment.

### Free-Text-Required / Stop-And-Wait

The StickS3 should not attempt full text entry. Instead:

- Show that the agent is waiting for a typed/user response.
- Offer host-provided quick replies if available.
- Allow opening/focusing the session on host.
- Later, allow `B hold` voice note recording as the practical arbitrary
  response path.

## Main Screens

Recommended first screens:

1. **Action screen**
   Highest-priority decision or blocking input requirement.

2. **Focused session**
   Project, branch, phase, model, context/budget, latest short message.

3. **Project/session list**
   One row/item focused at a time, with counts and status markers.

4. **Latest message**
   Paged compact text from host summary.

5. **Idle buddy/status**
   Existing pet/status behavior, battery, link, token stats.

6. **Settings/menu**
   Bluetooth, sound, language/font, DND/mute, reset, character settings.

## Protocol Sketch

Heartbeat/state snapshot:

```json
{
  "total": 4,
  "running": 2,
  "waiting": 1,
  "focused": "s_123",
  "sessions": [
    {
      "sid": "s_123",
      "project": "claude-desktop-buddy",
      "branch": "feature/connectors",
      "dirty": 2,
      "phase": "running",
      "model": "codex",
      "last": "editing firmware UI",
      "budget": 72,
      "started_at": 1777180100,
      "updated_at": 1777180820,
      "elapsed_s": 720
    }
  ],
  "pending": [
    {
      "id": "q_abc",
      "sid": "s_123",
      "kind": "single_choice",
      "title": "Choose connector mode",
      "body": "How should the bridge route this session?",
      "pending_since": 1777180780,
      "pending_s": 40,
      "options": [
        { "id": "ble", "label": "BLE", "desc": "Wireless buddy transport" },
        { "id": "usb", "label": "USB", "desc": "Serial transport" }
      ]
    }
  ],
  "event": {
    "kind": "complete",
    "sid": "s_123",
    "title": "Done",
    "text": "Build finished",
    "ttl_ms": 5000
  }
}
```

Device commands:

```json
{"cmd":"answer","id":"q_abc","choice":"ble"}
{"cmd":"answer","id":"q_abc","choices":["a","c"]}
{"cmd":"permission","id":"req_123","decision":"once"}
{"cmd":"defer","id":"q_abc"}
{"cmd":"focus","sid":"s_123"}
{"cmd":"event_dismiss","sid":"s_123"}
{"cmd":"mute","seconds":900}
```

Future microphone commands:

```json
{"cmd":"audio_begin","sid":"s_123","decision_id":"q_abc","format":"wav"}
{"cmd":"audio_chunk","id":"aud_123","d":"<base64>"}
{"cmd":"audio_end","id":"aud_123"}
```

The exact audio transport can be refined later. For larger files, USB or a
host-mediated BLE transfer with acknowledgements may be more reliable than
fire-and-forget chunks.

## Audio Plan

The audio work belongs in the build order, but not as the first dependency
for session display.

Phase 1:

- Use `M5.Speaker.tone()` patterns for event feedback.
- Validate volume, battery behavior, and BLE timing on hardware.
- Events: input required, complete, error, approved, denied, context warning.

Phase 2:

- Convert selected WAV assets before bundling.
- Prefer short mono PCM WAV files, for example 16-bit mono 22050 Hz.
- Trim silence and keep each clip small.
- Embed converted WAVs as `const uint8_t[] PROGMEM` arrays first.
- Use `M5.Speaker.playWav()` only with stable memory pointers.

Phase 3:

- Optional LittleFS sound packs.
- Load the full WAV into a persistent buffer and keep it alive until
  playback ends.

OpenPeon-style candidate sounds:

- input required: hover sound.
- approved: confirm sound.
- denied/error: cancel low sound.
- completion: pause or confirm sound.
- context warning: pause low sound.

## Implementation Plan

### Phase 0: Current Baseline

- Build current firmware for `m5sticks3`.
- Verify display, buttons, BLE pairing, battery, and speaker tone.
- Keep existing approval behavior working.

### Phase 1: Protocol And Host Model

- Define host-side session and pending-decision schemas.
- Keep old heartbeat fields backward-compatible.
- Add `sessions[]`, `focused`, `pending[]`, and `event`.
- Add session and decision timing fields such as `started_at`,
  `updated_at`, `waiting_since`, `pending_since`, `elapsed_s`, and
  `pending_s`.
- Add decision kinds: `permission`, `single_choice`, `multi_choice`,
  `notice`, `free_text_required`.
- Add `ttl_ms` event countdown support.

### Phase 2: Firmware Parser

- Extend `src/data.h` to parse compact session summaries.
- Add UTF-8-safe truncation before rendering arbitrary text.
- Increase line buffers if needed.
- Ignore unknown fields.
- Preserve existing minimal `prompt` behavior.

### Phase 3: StickS3 UI

- Add main state model:
  - action screen,
  - focused session,
  - session/project list,
  - latest message,
  - idle/status,
  - settings.
- Implement countdown overlay.
- Implement button grammar with `B hold` reserved for microphone.
- Keep font size no smaller than current `setTextSize(1)`.

### Phase 4: Basic Audio

- Add tone patterns for event kinds.
- Add settings for sound on/off and possibly quiet hours/DND.
- Verify on hardware.

### Phase 5: WAV Effects

- Select a small sound set.
- Add a conversion script or documented conversion command.
- Generate compact PCM WAV arrays.
- Play embedded WAV effects.

### Phase 6: CJK Font Support

- Add UTF-8 wrapping/truncation first.
- Test LittleFS font loading on StickS3.
- Try subsetted CJK font.
- Add language setting and CJK labels only after rendering is stable.

### Phase 7: Microphone Feedback

- Validate StickS3 mic support in M5Unified or add board config.
- Implement press-and-hold recording on `B hold`.
- Send audio to host.
- Host transcribes and attaches text to active decision/session.
- Host forwards resulting text to Claude/Codex/agent.

## Open Design Questions

- Should project list grouping be by `session_id`, by `cwd + branch`, or
  host-provided project id? Runtime should probably be session-first, with
  project metadata for display.
- Should `B double-click` cycle projects globally or cycle pending
  decisions first? Current recommendation: pending decisions first.
- Should completion overlays be per-session or global latest event only?
  Current recommendation: host sends one active event plus session id.
- How much CJK support is required for the first usable build: arbitrary
  Chinese content, Chinese UI labels, or only no-crash UTF-8 handling?
- Should audio recording be BLE-transferred from device to host, or should
  microphone support depend on USB serial first?
