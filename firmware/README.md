# ESP32 firmware reference

Optional **hardware desk-pet** reference for makers. This is **not** required
to use DevPet on your phone.

The mobile app and bridge protocol were **designed against this firmware**:
heartbeat fields, pet states, permission/choice intents, and session-console
extensions all trace back to the original M5StickC / StickS3 BLE buddy. Phone
users connect over **Wi‑Fi WebSocket** instead of BLE.

## What it does

- Pairs with **Claude Desktop** over BLE (Nordic UART) when developer mode is
  enabled (**Developer → Open Hardware Buddy…**)
- Renders ASCII species or 96×96 GIF character packs from LittleFS
- Shows session status, approvals, and activity on a small display

## Build & flash

PlatformIO project lives in **`firmware/`** — run all `pio` commands from this
directory, not the repo root.

```bash
cd firmware          # required; repo root has no platformio.ini
```

### Prerequisites

- [PlatformIO](https://platformio.org/) (`pio` on PATH)
- USB cable to the board
- For **M5 StickS3**: install the board USB driver if macOS does not show
  `/dev/cu.usbmodem*`

### Compile only

```bash
pio run                      # default env: m5stickc-plus
pio run -e m5sticks3         # M5 StickS3 (recommended)
pio run -e m5stickc-plus     # original M5StickC Plus
```

### Flash firmware

Connect the device, then:

```bash
pio run -e m5sticks3 -t upload
```

Other boards:

```bash
pio run -e m5stickc-plus -t upload
```

Wipe flash and reflash (fixes corrupt FS or bad NVS):

```bash
pio run -e m5sticks3 -t erase && pio run -e m5sticks3 -t upload
```

### M5 StickS3 bootloader note

StickS3 uses native USB-CDC — esptool cannot auto-reset into download mode.
If upload fails, enter bootloader manually:

1. Hold **Btn B**
2. Short-press **Power**
3. Release **Btn B**
4. Retry `pio run -e m5sticks3 -t upload`

Find the serial port:

```bash
ls /dev/cu.usbmodem*
```

### Flash GIF character pack (optional)

```bash
pio run -e m5sticks3 -t uploadfs
# or from repo root:
python3 tools/flash_character.py firmware/characters/bufo
```

### Serial monitor

```bash
pio device monitor -e m5sticks3
```

Hardware abstraction (`m5_compat.h`) merged from
[anthropics/claude-desktop-buddy](https://github.com/anthropics/claude-desktop-buddy):
StickS3 uses software RTC, `bdy*()` power/IMU helpers, and USB-CDC boot fixes;
StickC Plus keeps M5Unified for UTF-8/CJK fonts.

**Firmware-only changes** (upstream sync, board ports, `m5_compat`) land on
`feat/firmware-m5-compat`. Pull or rebase that branch before editing `firmware/`
so mobile/bridge work on `main` stays separate.

## Documentation

| Document | Content |
| --- | --- |
| [`../REFERENCE.md`](../REFERENCE.md) | BLE wire protocol (stable contract) |
| [`characters/bufo/`](characters/bufo/) | Example GIF character pack |
| Git history under `firmware/` | Controls, sounds, UTF-8/CJK, microphone |

You do not need the Expo app in `app/` to build a standalone BLE device.
