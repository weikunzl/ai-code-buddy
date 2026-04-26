# Handoff

Last updated: 2026-04-26

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

The immediate technical baseline is: this firmware already targets `m5sticks3`, and StickS3 hardware/library details are now documented before changing code. The session-console design is recorded in `docs/sticks3-session-console-design.md`, accepted architecture decisions for Milestone A are recorded in `docs/adr/`, and the formal design/implementation plan are recorded in `docs/superpowers/`. Milestone A Task 1 has been executed: `pio run -e m5sticks3` passed before firmware source changes. Milestone A Task 2 is complete, including review fixes for queued prompts on the same session. Milestone A Task 3 is complete: `tools/session_bridge.py` now has simulator frame generation, device JSON command parsing, git metadata helpers, stdout transport, and `--simulate --once`; `tools/test_session_bridge.py` covers simulator frames and device command RX; `tools/test_session_frames.py` prints representative firmware frames. Task 3 review cleanup added Python bytecode ignores for bridge test runs. Milestone A Task 4 is complete: the bridge now ingests Claude hook payloads through `apply_hook`, exposes a local HTTP hook server, emits rate-limited snapshots through a `BridgeRuntime`, parses device command lines through `LineReader`, and offers optional BLE transport behind a lazy `bleak` import. Task 4 review fixes now ensure blocking `PreToolUse` can publish pending state before waiting, `Stop` does not leave contradictory waiting prompts, and BLE writes are chunked before transmission. Milestone A Task 5 is complete after review correction: `src/data.h` now parses rich session/pending/event fields, clears stale sparse-heartbeat collections correctly, avoids resetting identical events on every frame, mirrors the first rich pending item back into the legacy prompt fields, and uses `8192`-byte line buffers with explicit overflow discard so current rich bridge heartbeats do not get truncated. Milestone A Task 6 is complete: `src/main.cpp` now adds rich action rendering, focused-session and session-list display modes, and routes HUD rendering through rich pending state when present. Milestone A Task 7 is complete: session-console button commands and alert tones are now wired, including single-choice answers, session focusing, session-page cycling, pending/event alerts, and the guard that prevents mirrored rich pending from producing a duplicate prompt chirp. Milestone A Task 8 is complete: short-lived event overlays now render with TTL progress, dismiss correctly with `BtnB`, and take precedence over underlying page controls. Task 9 documentation is complete in `README.md` and `REFERENCE.md`. Host-side verification is complete: `python3 tools/test_session_bridge.py`, `python3 tools/test_session_frames.py`, and `pio run -e m5sticks3` all passed. Follow-up hardware verification improved the state: `pio device list` detected `/dev/cu.usbmodem144301`, `pio run -e m5sticks3 -t upload` succeeded on that port, and user-observed BLE simulator behavior confirmed the on-device display path by showing the `Bash` request and then `Done`. During that verification two bridge simulator bugs were found and fixed: `tools/session_bridge.py --simulate` now honors `--transport ble`, and non-`--once` simulate mode now holds the pending request until a device decision arrives instead of auto-advancing immediately. Both paths are covered by regression tests. The current build baseline on `m5sticks3` is RAM `90508 / 327680` and Flash `1255621 / 4194304`.

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

1. Continue with interactive BLE verification on the connected StickS3. Re-run long-running `tools/session_bridge.py --transport ble --simulate`; it now holds the `Bash` request until the device responds and logs `[sim] decision=once` or `[sim] decision=deny` on the host side.

2. The unchanged firmware baseline already passed:

   ```bash
   pio run -e m5sticks3
   ```

3. Flash and verify board basics when hardware is ready:

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

6. Implement the smallest useful hook bridge slice:
   - add a Python daemon under `tools/` that receives Claude Code hooks,
   - track sessions by `session_id`,
   - collect `cwd`, project name, git branch, dirty count, recent hook phase, and pending approval,
   - push compact line-delimited JSON over BLE first, with USB serial enabled after StickS3 native USB RX is verified.

7. Extend `src/data.h` conservatively:
   - add optional `project`, `branch`, `dirty`, `model`, `assistant_msg`, `budget`,
   - add optional `sessions[]`,
   - extend `prompt` with `body`, `kind`, `options`, `project`, and short `sid`,
   - include optional timing fields like `started_at`, `updated_at`, `waiting_since`, `pending_since`, `elapsed_s`, and `pending_s`,
   - increase line buffers if richer heartbeats exceed the current 1024 byte cap.

8. Add a StickS3 compact work UI:
   - approval screen remains highest priority,
   - focused project/session status page,
   - short session list page,
   - latest assistant/message page,
   - existing pet/menu/status screens preserved where practical.

9. Add notification sound first, voice later:
   - short tone patterns for waiting approval, completion, denial, timeout, and DND,
   - after tone validation, replace simple tones with converted OpenPeon sound effects,
   - select 4-6 clips: input required, approve/ack, complete, error/deny, resource warning, optional session start,
   - convert selected WAVs offline to small mono PCM WAVs, preferably 16-bit mono 22050 Hz with silence trimmed,
   - prefer `const uint8_t[] PROGMEM` embedded WAV arrays for the first implementation,
   - use `M5.Speaker.playWav()` only with embedded bytes or a persistent in-memory buffer; it does not take a LittleFS path directly,
   - if using LittleFS later, load the selected WAV fully into a buffer and keep that buffer alive until `M5.Speaker.isPlaying()` reports playback is done,
   - defer spoken notices until speaker behavior is validated and a host-generated audio or fixed-phrase strategy is chosen.

## Cautions

- Do not rely on `BtnPWR` until tested on hardware.
- Do not assume microphone works through local M5Unified without checking the StickS3 branch or adding config.
- Do not assume native USB CDC RX is reliable on StickS3. Current firmware skips Serial RX under `BUDDY_BOARD_S3` because of phantom bytes; verify before making USB the default transport.
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

Continue implementation from Milestone A Task 5.

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
