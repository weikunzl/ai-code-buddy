# Handoff

Last updated: 2026-05-03

## Where To Resume

Start with:

- `docs/adr/README.md`
- `docs/superpowers/specs/2026-04-26-stick-s3-session-console-design.md`
- `docs/superpowers/plans/2026-04-26-stick-s3-session-console-milestone-a.md`
- `docs/sticks3-plus-reference.md`
- `docs/sticks3-session-console-design.md`
- `FINDINGS.md`
- `PROGRESS.md`
- `/Users/souler/Documents/m5-paper-buddy/docs/ARCHITECTURE.md`
- `/Users/souler/Documents/m5-paper-buddy/tools/claude_code_bridge.py`
- `/Users/souler/Documents/ccnotify-dot/ccnotify.py`
- `/Users/souler/Documents/ccnotify-dot/ccnotify/status_manager.py`
- `/Users/souler/Documents/openpeon-cute-minimal/openpeon.json`
- `/Users/souler/Documents/openpeon-cute-minimal/sounds/`
- `platformio.ini`
- `src/main.cpp`
- `src/data.h`

The immediate technical baseline is: this firmware already targets `m5sticks3`, and StickS3 hardware/library details are now documented before changing code. The session-console design is recorded in `docs/sticks3-session-console-design.md`, accepted architecture decisions for Milestone A are recorded in `docs/adr/`, and the formal design/implementation plan are recorded in `docs/superpowers/`. Milestone A is complete for the BLE simulator path, including interactive hardware verification of display, decision return, and event outcomes. Milestone B is now defined for native StickS3 USB CDC RX in:

- `docs/adr/0006-validate-stick-s3-usb-cdc-rx.md`
- `docs/superpowers/specs/2026-04-27-stick-s3-usb-cdc-rx-design.md`
- `docs/superpowers/plans/2026-04-27-stick-s3-usb-cdc-rx-milestone-b.md`

Milestone B is now complete. The earlier `_serialRxReady()` gating approach was wrong for this board/runtime and has been replaced with the actual working USB CDC fix:

- `src/main.cpp` explicitly initializes StickS3 native USB CDC with `Serial.setRxBufferSize(1024); Serial.begin(115200);`
- `src/main.cpp` keeps `Serial.setTxTimeoutMs(0)` so host-absent writes do not stall boot
- `src/data.h` now polls USB RX with `available() > 0` semantics and ignores `read() < 0`, which avoids the `HWCDC::available() == -1` busy-loop freeze
- `_LineBuf` still ignores bytes until a real JSON `{` arrives, so phantom USB noise does not corrupt framing
- `tools/session_bridge.py` now has a persistent `--transport serial` mode for StickS3 native USB
- `tools/test_serial.py` was upgraded to prefer the actual modem path and hold the port open long enough for prompt-sized frames

Current `m5sticks3` build baseline after the working USB slice is RAM `98700 / 327680` and Flash `1255861 / 4194304`.

The next milestone is now recorded for richer choice prompts:

- `docs/adr/0007-choice-prompts-after-usb-bridge.md`
- `docs/superpowers/specs/2026-04-28-stick-s3-choice-prompts-design.md`
- `docs/superpowers/plans/2026-04-28-stick-s3-choice-prompts-milestone-c.md`

Milestone C is now narrowed and partially complete:

- scope is end-to-end `single_choice`, not multi-choice
- `tools/session_bridge.py` now validates `choice` against pending option ids
- simulator profiles now cover `permission` and `single`
- protocol docs now define `single_choice` options and `{"cmd":"answer","id","choice"}`
- hardware verification over persistent USB serial confirmed `B` cycles options and `A` returns the selected option id to the host simulator

The next milestone is now recorded for bounded multi-choice prompts:

- `docs/adr/0008-separate-multi-choice-milestone.md`
- `docs/superpowers/specs/2026-04-28-stick-s3-multi-choice-prompts-design.md`
- `docs/superpowers/plans/2026-04-28-stick-s3-multi-choice-prompts-milestone-d.md`

Milestone D is now complete:

- bridge accepts and validates `choices[]` for `multi_choice`
- simulator profile `multi` exists
- firmware renders bounded multi-choice rows
- `A click` toggles, `B click` moves, `A hold` submits
- hardware verification over persistent USB serial confirmed end-to-end return of `['ble', 'usb']`

## Architecture Direction

- Use the M5Paper project as the main architecture reference:
  - hooks -> local Python bridge daemon -> USB/BLE JSON -> device,
  - daemon owns sessions, project metadata, prompt queue, transcript/model/context parsing,
  - device stays a view/controller and sends small commands back.
- Use `ccnotify-dot` as a secondary reference for hook phase tracking, SQLite aggregation, compact status rendering, and remote image/API push. Its `cwd + branch` aggregation is useful for status history, but runtime focus should probably stay keyed by Claude `session_id`.
- Use `openpeon-cute-minimal` as an event-sound reference. It is short UI sound effects, not spoken voice; treat it as a source for confirmation/attention/error tones.
- Avoid direct code copy from `m5-paper-buddy` unless relicensing is intentional; it is GPL-3.0 with explicit attribution/derivative obligations, while this repository is MIT.
- Favor clean, backward-compatible schema growth. Unknown JSON fields should remain ignorable by firmware.
- Treat the design phase as complete enough to begin implementation later. Do not copy the M5Paper touch-first UI; build the StickS3 as a compact session console that shows the next most actionable item.
- The first implementation target should be a minimal host bridge plus firmware parser/UI support for session summaries, pending decisions, timing metadata, countdown event overlays, and basic tone alerts.

## Suggested Next Steps

1. Treat Milestone B as complete and move to the next product slice.

2. Treat Milestone D as complete and move to the next product slice.
   - current state: permission, single-choice, and bounded multi-choice are all verified over the bridge/runtime
   - next practical step is a new slice, not more prompt-kind drift inside this one

3. The current firmware baseline passed:

   ```bash
   pio run -e m5sticks3
   ```

4. Flash when hardware is connected:

   ```bash
   pio run -e m5sticks3 -t upload
   ```

4. Add temporary serial diagnostics if needed for:
   - `M5.getBoard()`
   - display width/height
   - BtnA, BtnB, BtnPWR events
   - battery voltage and charging state
   - IMU enabled state and accel/gyro readings
   - speaker tone
   - microphone recording
   - IR TX/RX

5. Use `docs/sticks3-session-console-design.md` as the design baseline:
   - treat `docs/adr/README.md` and ADR-0001 through ADR-0005 as the implementation-planning contract,
   - use `docs/superpowers/specs/2026-04-26-stick-s3-session-console-design.md` as the formal design spec,
   - execute `docs/superpowers/plans/2026-04-26-stick-s3-session-console-milestone-a.md` task by task,
   - keep text no smaller than current `setTextSize(1)`,
   - do not clone the M5Paper touch UI,
   - reserve `B hold` for future microphone recording,
   - use countdown event overlays,
   - include host-provided elapsed/pending timing metadata,
   - treat Chinese/CJK font support as a separate UTF-8-safe rendering slice,
   - include audio conversion after tone-pattern validation.

6. Live bridge transport options are now:
   - BLE: `python3 tools/session_bridge.py --transport ble`
   - USB serial: `python3 tools/session_bridge.py --transport serial --serial-port /dev/tty.usbmodem...`

7. Continue the hook bridge and UI work from this verified base:
   - keep tracking sessions by `session_id`
   - keep the host as the source of truth for project/session/prompt state
   - use persistent USB serial for local debug and BLE for wireless operation

8. Milestone E is now complete for hook-produced choice prompts:
   - `docs/adr/0009-hook-produced-choice-prompts.md`
   - `docs/superpowers/specs/2026-04-28-stick-s3-hook-choice-prompts-design.md`
   - `docs/superpowers/plans/2026-04-28-stick-s3-hook-choice-prompts-milestone-e.md`
   - `Notification` may carry a bounded bridge-local
     `prompt` object
   - supported prompt kinds: `single_choice`, `multi_choice`
   - bridge returns plain JSON answers to the caller:
     - `{"decision":"usb"}`
     - `{"choices":["ble","usb"]}`
   - invalid prompt envelopes fall back to the existing plain-notification
     path
   - stale device decisions are cleared on pending-id reuse and on resolve

9. Extend `src/data.h` conservatively:
   - add optional `project`, `branch`, `dirty`, `model`, `assistant_msg`, `budget`,
   - add optional `sessions[]`,
   - extend `prompt` with `body`, `kind`, `options`, `project`, and short `sid`,
   - include optional timing fields like `started_at`, `updated_at`, `waiting_since`, `pending_since`, `elapsed_s`, and `pending_s`,
   - increase line buffers if richer heartbeats exceed the current 1024 byte cap.

10. Add a StickS3 compact work UI:
   - approval screen remains highest priority,
   - focused project/session status page,
   - short session list page,
   - latest assistant/message page,
   - existing pet/menu/status screens preserved where practical.

11. Add notification sound first, voice later:
   - short tone patterns for waiting approval, completion, denial, timeout, and DND,
   - after tone validation, replace simple tones with converted OpenPeon sound effects,
   - select 4-6 clips: input required, approve/ack, complete, error/deny, resource warning, optional session start,
   - convert selected WAVs offline to small mono PCM WAVs, preferably 16-bit mono 22050 Hz with silence trimmed,
   - prefer `const uint8_t[] PROGMEM` embedded WAV arrays for the first implementation,
   - use `M5.Speaker.playWav()` only with embedded bytes or a persistent in-memory buffer; it does not take a LittleFS path directly,
   - if using LittleFS later, load the selected WAV fully into a buffer and keep that buffer alive until `M5.Speaker.isPlaying()` reports playback is done,
   - defer spoken notices until speaker behavior is validated and a host-generated audio or fixed-phrase strategy is chosen.

12. Milestone F is now complete for real hook relay transport:
   - `tools/hook_relay.py` reads hook JSON from stdin and forwards it to the
     local bridge HTTP endpoint
   - it prints the bridge response body unchanged to stdout
   - it fails open by default with `{}` when the bridge is unavailable
   - `--strict` turns invalid stdin, bridge-unavailable, and invalid bridge
     response paths into non-zero failures
   - no bridge state logic was duplicated outside `tools/session_bridge.py`

13. The relay milestone is recorded in:
   - `docs/adr/0010-add-a-hook-relay-cli.md`
   - `docs/superpowers/specs/2026-04-28-hook-relay-cli-design.md`
   - `docs/superpowers/plans/2026-04-28-hook-relay-cli-milestone-f.md`

14. Milestone G is now complete for the producer helper:
   - `tools/post_notification_prompt.py` accepts a smaller producer-local
     payload and wraps it as `hook_event_name = "Notification"`
   - it reuses `tools/hook_relay.py` transport logic
   - invalid producer input fails non-zero
   - bridge failures are strict by default, with optional `--fail-open`
   - helper default timeout is `35s` so device decision waits are not cut
     off by a transport timeout

15. The producer-helper milestone is recorded in:
   - `docs/adr/0011-add-a-notification-prompt-helper.md`
   - `docs/superpowers/specs/2026-04-28-notification-prompt-helper-design.md`
   - `docs/superpowers/plans/2026-04-28-notification-prompt-helper-milestone-g.md`

16. Audio investigation status:
   - keep the `m5sticks3-speakerdiag` environment and `src/diagnostics/speaker_diag.cpp`; it is now the known-good low-level speaker probe
   - `src/main.cpp` now initializes speaker master/channel volume explicitly and uses raw cue playback with `waitForSpeakerStart(30)` fallback
   - real hardware boot self-test inside the full app proved both raw cues are audible
   - silent prompt arrival is now most likely explained by the persisted `sound` preference being off, because the normal prompt/event cue path respects `settings().sound`
   - the next user-facing verification step is simply: turn `sound` on in Settings and replay a `Bash` request
   - firmware now surfaces mute state directly:
     - normal HUD shows `mute` when `settings().sound` is off
     - `DEVICE` info page shows `sound on/off`
   - the next audio slice is already implemented in the repo but not yet heard on-device:
     - `tools/convert_openpeon_assets.py` generates `src/wav_assets.cpp`
     - current source selection is:
       - input required -> `/Users/souler/Documents/openpeon-cute-minimal/sounds/hover-sound.wav`
       - answer sent -> `/Users/souler/Documents/openpeon-cute-minimal/sounds/confirm-sound.wav`
       - complete -> `/Users/souler/Documents/openpeon-cute-minimal/sounds/cancel-sound.wav`
     - build/test passed and the larger image eventually flashed after reconnecting `/dev/cu.usbmodem144301`
     - hardware verification confirmed the `hover-sound.wav` arrival cue in the normal `Bash` prompt flow
     - source now also includes:
       - `toneAnswerSent()` mapped to `confirm-sound.wav`
       - `awaitingPromptClear` to suppress duplicate UI beeps after the first send
     - next resume step is to reconnect the StickS3 and retry `pio run -e m5sticks3 -t upload`, then verify:
       - `A` uses the converted acknowledge clip
       - repeated presses after first send stay silent until prompt clear
     - latest retry still failed mid-flash around one-third into the image, so if the next reconnect does not help, the practical fallback is to shrink embedded clips before another hardware attempt
     - that shrink fallback is now done:
       - clips are converted at `11025Hz`
       - each clip is capped at `4096` samples
       - flash size dropped to `1282533`
     - direct `esptool.py` at `115200` reached much farther than PlatformIO upload, but still died around `62%`
     - next resume step should be a hardware-side change, not another identical software retry:
       - different USB cable/port
       - direct motherboard port instead of hub/dock
       - then retry the direct `esptool.py` path first

16. Recommended next milestone after the producer helper:
   - bounded free-text prompt handling as its own separate slice
   - no on-device keyboard
   - use `notice` and `free_text_required`
   - allow optional quick replies and host-session focus

17. The bounded free-text milestone is now recorded in:
   - `docs/adr/0012-bound-free-text-to-notice-and-quick-replies.md`
   - `docs/superpowers/specs/2026-04-28-free-text-required-design.md`
   - `docs/superpowers/plans/2026-04-28-free-text-required-milestone-h.md`

18. Milestone H is now complete for bounded free-text-required handling:
   - bridge accepts `notice` and `free_text_required`
   - quick-reply `free_text_required` reuses scalar `choice` answers
   - optionless stop-and-wait prompts do not block on device response
   - `tools/post_notification_prompt.py` accepts the new kinds
   - StickS3 action UI renders:
     - `A: focus` for `notice` and optionless `free_text_required`
     - `A: send`, `B: next` for quick-reply `free_text_required`

19. Recommended next milestone after bounded free-text:
   - concrete end-to-end upstream workflow/config examples that use
     `tools/hook_relay.py` and `tools/post_notification_prompt.py`
   - prefer checked-in JSON payloads plus a smoke test
   - avoid claiming an exact upstream vendor config format

20. CJK layout tuning is now complete and hardware-verified:
   - prompt-active normal mode forces the buddy/character into `peek` scale
   - approval/action surfaces now render from `y=70` downward instead of as a smaller bottom card
   - prompt bodies no longer use transcript-style continuation indent
   - prompt CJK title/body/choice widths are wider than the generic transcript/session widths
   - direct USB Chinese prompt verification passed on hardware:
     - `操作没有互相挤压` rendered fully
     - body width utilization is fixed
     - buddy size is acceptable
     - option rows remain clean above the footer

21. Resume from the next milestone after verified CJK layout tuning, not from another prompt-fit workaround.
   Recommended next milestone:
   - host-side internationalized workflow/config examples and tests, or
   - microphone feasibility, depending on product priority

22. Host-side internationalized workflow/config coverage is now complete:
   - added checked-in multilingual examples under `docs/examples/`:
     - `hook-user-prompt-submit-zh.json`
     - `prompt-single-choice-zh.json`
     - `prompt-multi-choice-ja.json`
     - `prompt-free-text-required-ko.json`
   - `docs/upstream-workflow-examples.md` now documents those shell entry points
   - `tools/test_workflow_examples.py` now validates UTF-8 preservation through the real relay/helper boundaries

23. Verification for the multilingual workflow slice:
   - `python3 tools/test_workflow_examples.py`: PASS (`7` tests)
   - `python3 tools/test_hook_relay.py`: PASS (`7` tests)
   - `python3 tools/test_post_notification_prompt.py`: PASS (`9` tests)
   - `python3 -m py_compile tools/test_workflow_examples.py tools/test_hook_relay.py tools/test_post_notification_prompt.py tools/post_notification_prompt.py tools/hook_relay.py`: PASS

24. Resume from the next milestone after the verified multilingual host-workflow baseline.
   Recommended next milestone:
   - microphone feasibility, or
   - end-to-end hardware verification of multilingual upstream prompt flows if you want one more user-observed pass before branching into mic work

20. The runnable upstream examples milestone is now recorded in:
   - `docs/adr/0013-add-runnable-upstream-workflow-examples.md`
   - `docs/superpowers/specs/2026-04-28-upstream-workflow-examples-design.md`
   - `docs/superpowers/plans/2026-04-28-upstream-workflow-examples-milestone-i.md`

21. Milestone I is now complete for runnable upstream workflow examples:
   - checked-in payloads live in `docs/examples/`
   - the focused guide is `docs/upstream-workflow-examples.md`
   - smoke validation lives in `tools/test_workflow_examples.py`
   - examples cover:
     - `UserPromptSubmit` hook relay
     - `single_choice` prompt helper
     - `free_text_required` prompt helper

22. Recommended next phase after runnable examples:
   - concrete hardware verification of the new `notice` /
     `free_text_required` flows on the StickS3
   - use dedicated serial smoke profiles instead of ad hoc JSON edits

23. The stop-and-wait hardware-verification milestone is now recorded in:
   - `docs/adr/0014-verify-stop-and-wait-prompts-on-hardware.md`
   - `docs/superpowers/specs/2026-04-28-stop-and-wait-hardware-verification-design.md`
   - `docs/superpowers/plans/2026-04-28-stop-and-wait-hardware-verification-milestone-j.md`

24. Milestone J is now complete for stop-and-wait prompt hardware verification:
   - current firmware uploaded successfully to `/dev/cu.usbmodem144301`
   - `tools/test_serial.py` now has dedicated profiles:
     - `notice`
     - `free_text`
     - `free_text_choice`
   - user-observed hardware results:
     - `notice` rendered expected title/body and stop-and-wait footer
     - optionless `free_text_required` rendered `Need details` with `A: focus`
     - quick-reply `free_text_required` returned a real host decision through
       `tools/post_notification_prompt.py`: `{"decision":"tmp"}`

25. Recommended next phase after stop-and-wait verification:
   - centralize named tone patterns for prompt/event alerts,
   - keep WAV assets and microphone work for later,
   - or deeper host-side focus handling if you want visible host reaction to
     the `focus` intent during stop-and-wait prompts.

26. The tone-pattern milestone is now recorded in:
   - `docs/adr/0015-centralize-tone-patterns-before-wav-assets.md`
   - `docs/superpowers/specs/2026-04-29-tone-patterns-design.md`
   - `docs/superpowers/plans/2026-04-29-tone-patterns-milestone-k.md`

27. Milestone K is now complete for named tone patterns:
   - `src/main.cpp` now centralizes alert tones behind named helpers
   - prompt arrival and pending arrival use the same input-required tone
   - event overlay uses named complete / error / neutral tones
   - answer-sent, deny, and stop-and-wait focus acknowledgement no longer
     hardcode raw frequencies at each call site

28. Recommended next phase after named tones:
   - embed a first small WAV asset set and replace one or two named tone
     helpers with `playWav()`,
   - or begin microphone feasibility work if you want to explore voice-note
     response paths instead of host typing.

29. The first embedded-WAV milestone is now recorded in:
   - `docs/adr/0016-validate-first-embedded-wav-assets.md`
   - `docs/superpowers/specs/2026-04-29-first-embedded-wav-assets-design.md`

30. Milestone L is intentionally narrower than full sound replacement:
   - convert two short OpenPeon-derived source clips into embedded firmware
     assets
   - replace only `toneInputRequired()` and `toneComplete()`
   - keep deny/error/focus/answer-sent on tones until `playWav()` is proven
     on hardware

31. The next task after this docs boundary is implementation planning and then
    bounded firmware playback integration, followed by connected-device audio
    verification.

32. The Milestone L implementation plan is now recorded in:
   - `docs/superpowers/plans/2026-04-29-first-embedded-wav-assets-milestone-l.md`

33. The plan keeps the first `playWav()` slice narrow:
   - create `src/wav_assets.h` and `src/wav_assets.cpp`
   - switch only `toneInputRequired()` and `toneComplete()` to embedded WAV
     playback
   - add `tools/test_wav_assets.py`
   - verify with both `pio run -e m5sticks3` and connected-device audio
     checks

34. Milestone L implementation was explored and then intentionally backed out
    as a product path on this runtime:
   - `ecb43c8` `test: add wav asset smoke test`
   - `7f358fc` `feat: add embedded wav alert cues`
   - `69e1f8c` `fix: avoid duplicate wav prompt cues`
   - `f8325bf` `fix: regenerate embedded wav assets`
   - `aab820e` `fix: use raw pcm alert playback`

35. Real hardware outcome for Milestone L:
   - `playWav()` stayed silent on the connected StickS3
   - `playRaw()` with signed 16-bit PCM also stayed silent
   - a tiny diagnostic `playRaw()` with unsigned 8-bit raw samples still
     stayed silent
   - tone-backed paths remained audible the whole time

36. Current firmware state is intentionally restored to tone-backed alerts:
   - `toneInputRequired()` and `toneComplete()` are back on `tone()`
   - no embedded audio asset files remain in the tree
   - this keeps the device on the last known-good audible path

37. The next audio work should not retry embedded playback blindly. It needs a
    separate low-level investigation of M5Unified/M5StickS3 streamed audio,
    likely starting from a minimal standalone upstream speaker example on this
    exact board/runtime rather than the session-console firmware.

## Cautions

- Do not rely on `BtnPWR` until tested on hardware.
- Do not assume microphone works through local M5Unified without checking the StickS3 branch or adding config.
- Do not regress the `HWCDC` fix by reintroducing `while (Serial.available())` style polling. On this board/runtime, `available()` can be `-1` before RX init and will freeze the main loop if treated as truthy.
- Do not use one-shot open/write/close host probes for prompt-sized USB frames. Keep the CDC port open persistently or hold it open after writes; otherwise long frames can be truncated before the trailing newline reaches firmware.
- Re-enable external 5 V with `M5.Power.setExtOutput(true)` when testing Grove/Hat power or IR.
- Keep speaker volume below 75% on battery, per official docs.
- The OpenPeon files are 16-bit stereo 44.1 kHz PCM WAV and should be compatible in principle with M5Unified, but full-size files are 40-88 KB each. Downsample to mono for a practical firmware asset set.
- IR receive must use RMT and may require disabling the speaker amplifier.
- Update project comments that mention PY32 PMIC if we touch power code; StickS3 uses M5PM1.
- WiFi remote-control mode should be a later phase. BLE/USB hook interaction is the lower-risk base; WiFi adds pairing, auth, reconnect, and local-network security decisions.
- Remote control should be daemon-mediated with commands like `focus_session`, `toggle_dnd`, `permission`, and `status`, not firmware-side knowledge of Claude internals.

## Commit Status

The first documentation commit has been created:

```text
c33930d docs: record session console architecture
```

It includes:

- `AGENTS.md`
- `docs/sticks3-plus-reference.md`
- `docs/sticks3-session-console-design.md`
- `FINDINGS.md`
- `PROGRESS.md`
- `HANDOFF.md`
- `docs/adr/`
- `docs/superpowers/`

Continue implementation from the post-Milestone-B baseline.

Milestone A Task 2 is the bridge state model commit:

```text
feat: add session bridge state model
```

The Task 2 quality review fix is:

```text
fix: keep bridge session waiting for queued prompts
```

The Task 2 quality re-review fix is:

```text
fix: preserve oldest bridge pending age
```

The Task 2 third review fix is:

```text
fix: keep bridge upserts from clearing pending state
```

Milestone A Task 3 is the bridge simulator and device command RX commit:

```text
feat: add bridge simulator frames
```

Task 3 quality review cleanup also removed generated Python bytecode and added `.gitignore` entries for `__pycache__/` and `*.pyc`.

Milestone A Task 4 is the bridge hook runtime commit:

```text
feat: add bridge hook runtime
```

It adds hook handling, local HTTP runtime, optional BLE transport, CLI flags, and bridge tests for the hook flow. Continue implementation from Milestone A Task 5 after that commit is present.

Task 4 quality review fixes are recorded in:

```text
fix: publish bridge pending state promptly
```

## Current Resume Point

- The current connected StickS3 is flashed with the four-clip embedded-PCM OpenPeon build.
- The current connected StickS3 is flashed with the role-normalized four-clip embedded-PCM OpenPeon build plus UTF-8-safe, script-aware CJK console rendering.
- The repo now also contains the complete microphone upload implementation:
  - `tools/session_bridge.py` accepts `audio_begin`, ordered `audio_chunk`,
    `audio_end`, and `audio_cancel`
  - successful device uploads are written under `<session cwd>/.buddy_audio/`
    as `.wav` plus `.json` sidecar metadata
  - `src/main.cpp` maps `B hold` to bounded voice-note capture on StickS3,
    attaches it to the active pending decision or focused session, and streams
    `pcm_u8` / `8000Hz` chunks back over the existing BLE or USB bridge
- Resume from hardware verification of the latest behavior, not from another upload workaround:
  - input-required should play the converted `hover-sound.wav`
  - generic menu/navigation clicks should play the converted `hover-sound-low.wav`
  - answer-sent should play the converted `confirm-sound.wav`
  - complete should play the converted `cancel-sound.wav`
  - warning/reset/pairing cues are now named tone roles in code and docs
  - prompt bodies, transcript rows, session summaries, and event overlays now slice on UTF-8 codepoint boundaries and treat common CJK ranges as double-width
  - actual CJK glyph rendering now switches by script onto bundled `efont` faces:
    - Han -> `efontCN_10` / `efontCN_12`
    - Japanese -> `efontJA_10` / `efontJA_12`
    - Korean -> `efontKR_10` / `efontKR_12`
  - repeated button presses after the first send should be ignored until the prompt clears
  - microphone still needs real hardware verification:
    - start the bridge over serial or BLE
    - hold `B` on the StickS3 for a few seconds
    - release `B`
    - confirm a `Voice Note` event returns to the device
    - confirm `<session cwd>/.buddy_audio/` contains a `.wav` and `.json`
      sidecar for that capture
