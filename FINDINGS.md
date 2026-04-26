# Findings

Last updated: 2026-04-26

## Repository

- This repo is a PlatformIO ESP32 firmware reference for a Claude hardware buddy.
- Core firmware is in `src/`; ASCII buddy renderers are in `src/buddies/`.
- `platformio.ini` has two environments: `m5stickc-plus` and `m5sticks3`.
- Utility scripts in `tools/` are hardware smoke tests and character upload helpers, not a formal unit test suite.
- Existing contribution guidance says this repo should accept narrow reference fixes and protocol documentation corrections, not broad feature expansion.
- Current firmware is still mostly device-local: `src/data.h` tracks simple heartbeat counts, transcript lines, and a minimal approval prompt (`id`, `tool`, `hint`). There is no host-side daemon in this repo yet for Claude Code hooks, multi-project aggregation, or richer approval bodies.
- `src/main.cpp` already has StickS3-oriented UI affordances worth preserving: screen modes, menus, speaker tones, BLE passkey display, approval/deny button handling, GIF/ASCII buddy rendering, IMU reactions, and low-power screen behavior.

## Local Libraries

- Local M5 libraries are available at:
  - `/Users/souler/Documents/M5Unified`
  - `/Users/souler/Documents/M5GFX`
- Local M5GFX/M5Unified expose `board_M5StickS3`; no separate `board_M5StickS3Plus` identifier was found.
- Local M5Unified maps StickS3 BtnA/BtnB to `GPIO11` and `GPIO12`.
- Local M5GFX configures StickS3 display as ST7789, `135 x 240`, using `GPIO39/40/45/41/21` plus backlight `GPIO38`.
- Local M5Unified configures StickS3 speaker over I2S on `GPIO18/17/15/14`.

## Official StickS3 Specs

- Official M5Stack page: `https://docs.m5stack.com/zh_CN/core/StickS3`
- Confirmed board: StickS3 SKU `K150`.
- SoC: `ESP32-S3-PICO-1-N8R8`, 8 MB Flash, 8 MB Octal PSRAM.
- Display: `ST7789P3`, `135 x 240`, 1.14 inch LCD.
- IMU: `BMI270`; power manager: `M5PM1`.
- Audio: `ES8311`, MEMS mic, `AW8737` amp, `8 ohm / 1 W` speaker.
- IR TX/RX are present; official pins are `GPIO46` and `GPIO42`.
- Battery is 250 mAh.

## M5Paper Buddy Reference

- Reviewed `/Users/souler/Documents/m5-paper-buddy`.
- Its most useful architecture is the three-layer split:
  - Claude Code hooks post to a local Python bridge daemon.
  - The daemon owns session/project/prompt state and pushes line-delimited JSON over USB serial or BLE Nordic UART.
  - Firmware is mostly a view/controller: render dashboard/approval/settings, send permission/focus commands back.
- The Paper bridge adds practical fields beyond the original desktop buddy protocol: `project`, `branch`, `dirty`, `model`, `assistant_msg`, `budget`, `sessions[]`, and richer `prompt.body`, `prompt.kind`, `prompt.options`.
- It handles multi-session approval with a FIFO pending prompt queue and per-prompt `threading.Event`, which is a good model for hook-driven hardware approval.
- It rate-limits heartbeats to 1 Hz and keeps a 10 second idle heartbeat. This is important for ESP32 stability under busy hook streams.
- The Paper firmware grows line buffers to 2560 bytes and treats unknown JSON fields as optional, preserving backward compatibility while allowing richer heartbeats.
- Direct code reuse needs care: `m5-paper-buddy` is GPL-3.0 with explicit attribution/derivative obligations, while this repo is MIT. Prefer clean reimplementation of the architecture unless relicensing is intentional.

## CCNotify Dot Reference

- Reviewed `/Users/souler/Documents/ccnotify-dot`.
- It is a useful host-side reference for hook ingestion, phase tracking, persistent task state, image rendering, and remote display push.
- `ccnotify.py` reads hook JSON from stdin and maps events into phases:
  - `UserPromptSubmit` -> `running`
  - user-interaction `Notification` keywords -> `waiting`
  - `Stop` -> `done` or `error`
  - `PostToolUseFailure` is logged but does not mark the whole task failed.
- `ccnotify/status_manager.py` stores aggregated task state in SQLite, keyed by `cwd + branch`. That is useful for multi-project status, but this firmware should probably key runtime focus by Claude `session_id` and use `cwd/project/branch` as metadata to avoid collapsing two sessions in the same repo.
- `ccnotify/image_generator.py` shows a compact 296x152 e-ink layout with CJK fonts, project/branch truncation, status symbols, and relative age. The visual density is a useful reference for StickS3 pager screens, even though StickS3 should receive JSON state rather than pre-rendered images.
- `ccnotify/api_client.py` pushes generated images to a remote Quote/0 API with retry. This is relevant to future WiFi/remote-control support, but the first StickS3 implementation should stay USB/BLE based for reliability and latency.

## OpenPeon Sound Reference

- Reviewed `/Users/souler/Documents/openpeon-cute-minimal`.
- It is a minimal OpenPeon/CESP sound pack, not a spoken voice pack. It maps short UI sounds to event categories such as `session.start`, `task.acknowledge`, `task.complete`, `task.error`, `input.required`, `resource.limit`, and `user.spam`.
- The assets are standard RIFF/WAVE PCM files: 16-bit, stereo, 44.1 kHz. The longer files are about 0.5 seconds and 88 KB each; the shorter pause files are about 0.23 seconds and 40 KB each.
- M5Unified exposes `M5.Speaker.playWav(const uint8_t* wav_data, size_t data_len, ...)` and accepts PCM WAV headers with 8-16 bits and 1-2 channels, so the format is conceptually compatible with StickS3 playback.
- Practical caveat: `playWav()` takes a memory pointer, not a file path/stream. If using LittleFS assets, firmware should load each WAV into a persistent buffer for the duration of playback, or convert selected sounds into compiled byte arrays.
- The sound sample license is CC0 per `sounds/LICENSE`; the pack metadata/README says MIT. Still preserve attribution in docs if assets are bundled.

## Recommended Audio Path

- Phase 1 should use simple `M5.Speaker.tone()` patterns for core events while hardware volume, battery behavior, and speaker reliability are verified.
- Phase 2 should use OpenPeon-style event sounds, not spoken voice:
  - choose 4-6 short sounds for `input.required`, `task.acknowledge`, `task.complete`, `task.error`, `resource.limit`, and optional `session.start`,
  - convert them offline to mono lower-rate PCM WAV, preferably 16-bit mono 22050 Hz; use 8-bit mono 16000/22050 Hz only if flash/RAM pressure matters,
  - keep each clip under roughly 20-50 KB after conversion and trim silence,
  - preserve the WAV header so `M5.Speaker.playWav()` can parse the format,
  - first implementation can embed converted WAVs as `const uint8_t[] PROGMEM` arrays for deterministic playback and simpler lifetime management,
  - if using LittleFS later, load the whole selected file into a persistent buffer before `playWav()` and keep it alive until `M5.Speaker.isPlaying()` is false.
- Event mapping suggestion:
  - `input.required` / approval pending -> hover sound,
  - approval accepted -> confirm sound,
  - denial or error -> cancel low sound,
  - task complete -> pause or cancel sound,
  - resource/context warning -> pause low sound.
- Spoken notices should be a later phase. If needed, prefer pre-rendered short WAV phrases or host-generated clips over on-device TTS.

## Architecture Suggestions

- Add a host bridge first, before WiFi. The bridge should consume Claude Code hooks, own state, and push compact JSON heartbeats to StickS3 over USB/BLE.
- Keep the device firmware as a small view/controller. Persist only user preferences and local stats in NVS; do not make firmware the session database.
- Extend the current JSON schema in a backward-compatible way rather than replacing it. Start with project/session metadata, focused session, prompt body/kind/options, model, assistant message, and context budget.
- On the 135x240 StickS3 screen, use paged/compact views instead of cloning the M5Paper dashboard:
  - approval view,
  - focused project/session status,
  - session list,
  - latest assistant/message,
  - settings/transport/status.
- Use speaker alerts before full voice features. Start with tone patterns, then converted OpenPeon-style sound effects. Treat "voice" as a later feature unless it means pre-rendered short WAV phrases.
- Treat microphone and WiFi as second phase work. Mic needs hardware/library validation; WiFi remote mode adds pairing/security/state-sync complexity that BLE/USB avoids.
- Remote control should be daemon-mediated. Device commands should be intents such as `focus_session`, `toggle_dnd`, `permission`, `status`, or future `pause_alerts`, not direct Claude internals.
- The current StickS3 session-console design discussion is recorded in `docs/sticks3-session-console-design.md`.
- The design phase is complete enough to start implementation later from the documented phase plan.
- Font size should not go below the current built-in `setTextSize(1)` baseline.
- Chinese/CJK rendering should be added deliberately: first make user text UTF-8 safe, then test a LittleFS-loaded subset font on StickS3. M5Paper's full `cjk.ttf` is about 3.4 MB and may be too costly once GIFs and sounds share the filesystem.
- Reserve a button gesture for later microphone recording. Current recommendation is `B hold`, with press-and-hold-to-record attaching audio feedback to the active decision or focused session.
- Temporary event screens should use countdown/TTL behavior and return to the previous main state when expired or dismissed.
- Heartbeat/session snapshots should include timing metadata from the host, such as session start/update times and pending-decision age. Firmware should display elapsed/pending time for user context, while host-side ranking remains authoritative.
- Audio conversion is part of the implementation plan: start with `M5.Speaker.tone()` validation, then convert selected WAVs to compact mono PCM WAV assets before embedding or loading them.

## Later Implementation Starting Point

- Start from `docs/sticks3-session-console-design.md`, not from the M5Paper UI.
- Milestone A Task 1 has been executed: `pio run -e m5sticks3` passed before any firmware source changes.
- Milestone A Task 2 has been executed: the initial host-side `BridgeState` model and executable Python smoke tests exist under `tools/`. The model intentionally keeps FIFO pending decisions and focused-session selection host-side before any firmware parser/UI changes.
- Task 2 review clarified a bridge state constraint: resolving one pending item must not mark a session `running` while another pending item for the same `sid` remains. `waiting_since` should be derived from the oldest remaining pending item for that same session.
- Task 2 re-review clarified the same constraint also applies at queue time: adding a newer pending item for a session must not reset `waiting_since`; same-session pending age should always come from the oldest queued prompt.
- Task 2 third review clarified the same constraint also applies to later session upserts: an incoming same-session `phase="running"` update must not clear unresolved pending state. `BridgeState` now centralizes oldest-pending derivation for upsert, queue, and resolve paths.
- Milestone A Task 3 has been executed: the bridge can now emit canned simulator frames for running, pending permission, and completion event states, and it can parse newline-delimited device JSON commands back into `BridgeState.handle_device_command()`.
- `tools/test_session_frames.py` is a host-side smoke tool for representative firmware frames; it does not exercise firmware parsing yet.
- Python bridge tests generate `__pycache__/`; `.gitignore` now ignores `__pycache__/` and `*.pyc` so later Python tasks do not leave generated cache files in the worktree.
- Milestone A Task 4 has been executed: the bridge can now map Claude hook events into session state (`UserPromptSubmit`/`SessionStart` running, `PreToolUse` pending permission, `Stop` completion event, simple `Notification` phase updates), serve hooks over local HTTP, emit snapshots through stdout or optional BLE, and consume device command lines through `LineReader`.
- BLE remains optional host functionality. `bleak` is imported only inside `BLETransport._thread_main()`, so unit tests and stdout simulation do not require the dependency.
- Task 4 quality review clarified three bridge runtime constraints:
  - blocking `PreToolUse` must publish pending state before waiting for a device decision,
  - `Stop` must not leave same-session pending prompts active while emitting a completion event,
  - BLE writes need chunking before richer heartbeat frames are practical.
- Milestone A Task 5 has been executed at the parser layer: `src/data.h` now accepts focused project/session metadata, bounded `sessions[]`, bounded `pending[]`, and `event` objects while still preserving the legacy `prompt` path by mirroring the first rich pending item.
- The bridge emits sparse heartbeats: it omits `sessions`, `pending`, and `event` when those collections are empty. The firmware parser therefore has to clear stale `sessions[]` and `pending[]` when those keys disappear instead of treating absence as "keep old state".
- Repeated identical `event` frames from the bridge must not reset `receivedMs` or bump `eventGen`, otherwise later tone/event-overlay logic will retrigger on every heartbeat and the TTL countdown will never advance.
- The current bridge payload envelope is much larger than the original Task 5 estimate. A max-shape synthetic heartbeat built from the current `tools/session_bridge.py` state model measured `5456` bytes, so the firmware line buffers need materially more than `2560` bytes to avoid truncating valid JSON.
- `_LineBuf` must treat overflow as a discard condition until newline. Continuing to append until full and then parsing the truncated prefix is worse than dropping the frame, because it turns a size mismatch into undefined partial state updates.
- The richer parser and `8192`-byte line buffers still compile comfortably on `m5sticks3`: RAM `90500 / 327680`, Flash `1252677 / 4194304`.
- Task 6 can stay narrowly presentational in `src/main.cpp`: rich action, focused-session, and session-list rendering fit the existing sprite/view structure without forcing an early file split or a broader UI refactor.
- The new session screens are intentionally incomplete until Task 7. `lastPendingGen`, `lastEventGen`, and the `A: focus` / `B: next` affordances exist now, but the actual device command routing and alert-tone behaviors still need to be wired before hardware behavior matches the labels.
- Rich pending now mirrors into the legacy prompt fields, so prompt-arrival alerts have to distinguish between legacy-only prompt traffic and rich `pending[]` arrivals. Without that guard, the device will chirp twice for the same decision.
- Session-console commands are now wired from the device side, but command JSON is still built with raw `%s` interpolation in `src/main.cpp`. If prompt ids or choice labels ever contain quotes or backslashes, the command helpers will need string escaping.
- The current completion-event alert uses a deliberate `delay(80)` between tones. That is acceptable for Milestone A, but it is still a small blocking pause in the main loop and should stay in mind if later interactions become more timing-sensitive.
- The event overlay behaves correctly only if dismissal takes precedence over the underlying page controls. Putting the dismiss branch after screen-specific `BtnB` handlers would leave a visible overlay that the user cannot clear without also paging the hidden screen below it.
- The current `event_dismiss` path still sends an empty `sid`, matching the present bridge behavior. If host-side dismissal becomes session-specific later, the device path will need to pass through `tama.event.sid`.
- Overlay text currently uses a simple fixed split (`17` chars per line). That is good enough for Milestone A, but long unbroken strings will still truncate rather than wrap.
- As of this resume point, software verification is green but hardware verification is still pending. `python3 tools/test_session_bridge.py`, `python3 tools/test_session_frames.py`, and `pio run -e m5sticks3` all passed, while `pio device list` exposed no uploadable StickS3 serial device in this workspace.
- Hardware reachability changed later in the session: `pio device list` detected `/dev/cu.usbmodem144301`, and `pio run -e m5sticks3 -t upload` succeeded against that port.
- Verification uncovered a bridge CLI bug: `tools/session_bridge.py --simulate --transport ble` did not actually use BLE because the simulate path bypassed transport selection. That path is now fixed and covered by a regression test.
- User-observed hardware behavior now confirms the BLE display path: running the simulator produced the expected `Bash` request on-device followed by the `Done` event state.
- The original non-`--once` simulator was also not suitable for validating button return traffic: it auto-advanced through the canned frames instead of holding the pending request. That path now waits for a device decision and logs the received `once`/`deny` result on the host side.
- Even with the transport fix, fully automated BLE confirmation from this workspace is still not reliable enough to record PASS. A temporary local `bleak`-based probe did not produce a clean observable confirmation, so end-to-end BLE behavior still needs direct device observation when resumed.
- First practical code slice should be a minimal bridge/state schema and firmware parser changes, preserving compatibility with the current simple heartbeat.
- Second slice should be StickS3 UI state/pages for action, focused session, session list, latest message, and idle/status.
- Third slice should add tone alerts and countdown overlays before richer WAV effects, CJK font loading, or microphone recording.

## Open Verification Items

- `BtnPWR` app-level click behavior needs hardware testing.
- Local M5Unified StickS3 branch does not clearly configure internal mic despite official MEMS mic hardware.
- IR receive requires ESP32 RMT and speaker amplifier disabled.
- Project comments still mention PY32 PMIC in places; official and local library sources indicate M5PM1 for StickS3.
- Native USB serial behavior on StickS3 needs hardware testing before relying on USB as the primary command channel. Current code skips Serial RX on `BUDDY_BOARD_S3` due to phantom bytes, while a hook bridge would benefit from reliable USB.
- Speaker and mic behavior should be validated on battery and USB power before adding notice voice or push-to-talk flows.
