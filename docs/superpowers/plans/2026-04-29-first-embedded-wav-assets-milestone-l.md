# First Embedded WAV Assets Milestone L Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate StickS3 in-memory WAV playback by embedding two short UI clips and replacing only the `input required` and `complete` alert helpers.

**Architecture:** Keep the current named-helper boundary in `src/main.cpp` and move the new asset bytes into a dedicated `src/wav_assets.*` unit. Use converted mono PCM WAV arrays in stable static storage so `M5.Speaker.playWav()` can be called without changing prompt/event call sites.

**Tech Stack:** PlatformIO, Arduino C++, M5Unified speaker APIs, macOS `afconvert`, `xxd`, Python 3 `unittest`

---

## File Map

- Create: `src/wav_assets.h`
  - declarations for the two embedded WAV arrays and their lengths
- Create: `src/wav_assets.cpp`
  - definitions for the converted `input required` and `complete` WAV bytes
- Create: `tools/test_wav_assets.py`
  - smoke test for asset declarations, RIFF/WAVE signatures, and helper call-site wiring
- Modify: `src/main.cpp`
  - include the asset header and switch two named helpers to `playWav()`
- Modify: `docs/adr/README.md`
  - index the Milestone L plan
- Modify: `FINDINGS.md`
  - record conversion assumptions and verification findings
- Modify: `HANDOFF.md`
  - point future resumes at Milestone L implementation and hardware audio verification
- Modify: `PROGRESS.md`
  - record the plan boundary and later implementation results

### Task 1: Record The Milestone L Plan

**Files:**
- Create: `docs/superpowers/plans/2026-04-29-first-embedded-wav-assets-milestone-l.md`
- Modify: `docs/adr/README.md`
- Modify: `FINDINGS.md`
- Modify: `HANDOFF.md`
- Modify: `PROGRESS.md`

- [ ] **Step 1: Add the plan document**

```markdown
# First Embedded WAV Assets Milestone L Implementation Plan
...
```

- [ ] **Step 2: Link the plan from the ADR index**

Add this entry to `docs/adr/README.md` after the Milestone K plan link:

```markdown
The next implementation plan after named tone patterns is:

- `docs/superpowers/plans/2026-04-29-first-embedded-wav-assets-milestone-l.md`
```

- [ ] **Step 3: Update resume notes for the new plan boundary**

Append Milestone L plan references to:

```markdown
FINDINGS.md
HANDOFF.md
PROGRESS.md
```

Expected notes:

- Milestone L is scoped to two converted embedded WAV cues
- only `toneInputRequired()` and `toneComplete()` are changing
- implementation should keep other helpers on tones

- [ ] **Step 4: Commit the docs boundary**

Run:

```bash
git add docs/superpowers/plans/2026-04-29-first-embedded-wav-assets-milestone-l.md \
  docs/adr/README.md FINDINGS.md HANDOFF.md PROGRESS.md
git commit -m "docs: add first embedded wav plan"
```

Expected: a new docs-only commit for the Milestone L plan boundary.

### Task 2: Add A Failing WAV Asset Smoke Test

**Files:**
- Create: `tools/test_wav_assets.py`
- Test: `tools/test_wav_assets.py`

- [ ] **Step 1: Write the failing test**

Create `tools/test_wav_assets.py`:

```python
#!/usr/bin/env python3
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
HEADER = ROOT / "src" / "wav_assets.h"
SOURCE = ROOT / "src" / "wav_assets.cpp"
MAIN = ROOT / "src" / "main.cpp"


class WavAssetTests(unittest.TestCase):
    def test_asset_unit_declares_both_wavs(self):
        text = HEADER.read_text()
        self.assertIn("kInputRequiredWav", text)
        self.assertIn("kInputRequiredWavLen", text)
        self.assertIn("kCompleteWav", text)
        self.assertIn("kCompleteWavLen", text)

    def test_asset_source_contains_riff_wave_signatures(self):
        text = SOURCE.read_text()
        self.assertIn("0x52, 0x49, 0x46, 0x46", text)
        self.assertIn("0x57, 0x41, 0x56, 0x45", text)

    def test_main_uses_playwav_for_two_named_helpers(self):
        text = MAIN.read_text()
        self.assertRegex(
            text,
            r"static void toneInputRequired\\(\\) \\{\\s*if \\(settings\\(\\)\\.sound\\) M5\\.Speaker\\.playWav\\(kInputRequiredWav, kInputRequiredWavLen\\);\\s*\\}",
        )
        self.assertRegex(
            text,
            r"static void toneComplete\\(\\) \\{\\s*if \\(settings\\(\\)\\.sound\\) M5\\.Speaker\\.playWav\\(kCompleteWav, kCompleteWavLen\\);\\s*\\}",
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
python3 tools/test_wav_assets.py
```

Expected: `FAIL` because `src/wav_assets.h` and `src/wav_assets.cpp` do not exist yet and `src/main.cpp` still uses `beep()`.

- [ ] **Step 3: Commit nothing yet**

Do not commit on red. Move directly to the minimal implementation task.

### Task 3: Add Embedded WAV Assets And Wire The Two Helpers

**Files:**
- Create: `src/wav_assets.h`
- Create: `src/wav_assets.cpp`
- Modify: `src/main.cpp`
- Test: `tools/test_wav_assets.py`

- [ ] **Step 1: Convert the two source clips to firmware-friendly WAV files**

Run:

```bash
mkdir -p /tmp/cdb-wav-assets
afconvert -f WAVE -d LEI16@22050 -c 1 \
  /Users/souler/Documents/openpeon-cute-minimal/sounds/hover-sound.wav \
  /tmp/cdb-wav-assets/input-required.wav
afconvert -f WAVE -d LEI16@22050 -c 1 \
  /Users/souler/Documents/openpeon-cute-minimal/sounds/confirm-sound.wav \
  /tmp/cdb-wav-assets/complete.wav
afinfo /tmp/cdb-wav-assets/input-required.wav
afinfo /tmp/cdb-wav-assets/complete.wav
```

Expected:

- `Data format: 1 ch, 22050 Hz, Int16`
- roughly `0.5 sec` duration each
- no source files copied into the repo

- [ ] **Step 2: Generate a dedicated asset source file**

Use `xxd -i` as the base and rename the generated symbols:

```bash
xxd -i /tmp/cdb-wav-assets/input-required.wav > /tmp/cdb-wav-assets/input-required.inc
xxd -i /tmp/cdb-wav-assets/complete.wav > /tmp/cdb-wav-assets/complete.inc
```

Create `src/wav_assets.h`:

```cpp
#pragma once

#include <stddef.h>
#include <stdint.h>

extern const uint8_t kInputRequiredWav[];
extern const size_t kInputRequiredWavLen;

extern const uint8_t kCompleteWav[];
extern const size_t kCompleteWavLen;
```

Create `src/wav_assets.cpp` with two `const uint8_t[]` arrays and `size_t` lengths:

```cpp
#include "wav_assets.h"

const uint8_t kInputRequiredWav[] = {
  /* xxd-generated bytes */
};

const size_t kInputRequiredWavLen = sizeof(kInputRequiredWav);

const uint8_t kCompleteWav[] = {
  /* xxd-generated bytes */
};

const size_t kCompleteWavLen = sizeof(kCompleteWav);
```

- [ ] **Step 3: Switch the two named helpers to WAV playback**

Modify `src/main.cpp`:

```cpp
#include "wav_assets.h"
```

Replace the two helper bodies:

```cpp
static void toneInputRequired() {
  if (settings().sound) M5.Speaker.playWav(kInputRequiredWav, kInputRequiredWavLen);
}

static void toneComplete() {
  if (settings().sound) M5.Speaker.playWav(kCompleteWav, kCompleteWavLen);
}
```

Leave `toneAnswerSent()`, `toneDenied()`, `toneFocusAck()`, `toneEventError()`, and `toneEventNeutral()` unchanged.

- [ ] **Step 4: Run the WAV smoke test to verify it passes**

Run:

```bash
python3 tools/test_wav_assets.py
```

Expected: `OK`

- [ ] **Step 5: Build firmware to verify the new asset unit links**

Run:

```bash
pio run -e m5sticks3
```

Expected: `SUCCESS` with a valid RAM/flash summary and no unresolved speaker symbols.

- [ ] **Step 6: Commit the implementation slice**

Run:

```bash
git add src/wav_assets.h src/wav_assets.cpp src/main.cpp tools/test_wav_assets.py
git commit -m "feat: add embedded wav alert cues"
```

Expected: one firmware/test commit containing the two-cue WAV integration.

### Task 4: Verify On Hardware And Update Resume Notes

**Files:**
- Modify: `FINDINGS.md`
- Modify: `HANDOFF.md`
- Modify: `PROGRESS.md`
- Test: `tools/test_wav_assets.py`

- [ ] **Step 1: Flash the connected StickS3**

Run:

```bash
pio run -e m5sticks3 -t upload
```

Expected: `SUCCESS`

- [ ] **Step 2: Trigger the input-required WAV cue**

Run a prompt-producing path that already exists in the repo:

```bash
.venv-session-bridge/bin/python tools/session_bridge.py --transport serial --serial-port /dev/tty.usbmodem144301 --simulate
```

Expected on device:

- prompt/pending screen appears
- `input required` sound is now a WAV clip, not the old single beep

- [ ] **Step 3: Trigger the complete-event WAV cue**

While the simulator is still running, press `A` on the device to approve the
simulated prompt.

Expected:

- the host logs the decision return
- the device shows the completion outcome
- the `complete` sound is now a WAV clip, not the old two-tone rise

- [ ] **Step 4: Record the hardware result in resume notes**

Update:

```markdown
FINDINGS.md
HANDOFF.md
PROGRESS.md
```

Record:

- whether both WAV cues were audible
- whether the device stayed responsive
- updated build size after embedding the assets

- [ ] **Step 5: Commit the verification slice**

Run:

```bash
git add FINDINGS.md HANDOFF.md PROGRESS.md
git commit -m "test: verify embedded wav alert cues"
```

Expected: one verification/docs commit with the connected-device outcome.

## Self-Review

- Spec coverage: this plan covers the dedicated asset unit, two-cue WAV conversion, helper-only playback changes, build verification, and connected-device audio verification from the Milestone L spec.
- Placeholder scan: no `TODO`/`TBD` placeholders remain; all file paths, commands, and helper names are explicit.
- Type consistency: the plan consistently uses `kInputRequiredWav`, `kInputRequiredWavLen`, `kCompleteWav`, and `kCompleteWavLen` across the asset unit, smoke test, and `src/main.cpp`.
