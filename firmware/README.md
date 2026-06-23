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

```bash
cd firmware
pio run -t upload
# M5StickC Plus: pio run -e m5stickc-plus -t upload
# M5 StickS3:     pio run -e m5sticks3 -t upload
```

## Documentation

| Document | Content |
| --- | --- |
| [`../REFERENCE.md`](../REFERENCE.md) | BLE wire protocol (stable contract) |
| [`characters/bufo/`](characters/bufo/) | Example GIF character pack |
| Git history under `firmware/` | Controls, sounds, UTF-8/CJK, microphone |

You do not need the Expo app in `app/` to build a standalone BLE device.
