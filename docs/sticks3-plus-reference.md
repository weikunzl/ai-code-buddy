# StickS3 Capability Notes

These notes summarize the official StickS3 hardware specification and what the locally checked-out M5 libraries expose for this board. Sources:

- Official M5Stack StickS3 docs: `https://docs.m5stack.com/zh_CN/core/StickS3`
- `/Users/souler/Documents/M5Unified`
- `/Users/souler/Documents/M5GFX`

Naming note: the official page is `StickS3` SKU `K150`. The local code exposes `board_M5StickS3`; it does not define a separate `board_M5StickS3Plus` identifier.

## Official Hardware Summary

- SoC: `ESP32-S3-PICO-1-N8R8`, dual-core Xtensa LX7 up to 240 MHz
- Memory: 8 MB Flash, 8 MB Octal PSRAM
- Wireless: 2.4 GHz Wi-Fi
- Display: `ST7789P3`, `135 x 240`, 1.14 inch LCD
- IMU: `BMI270` 6-axis sensor
- Power manager: `M5PM1`
- Audio: `ES8311` 24-bit I2S codec, MEMS microphone, `AW8737` amplifier, `8 ohm / 1 W` speaker
- IR: integrated transmitter and receiver
- Battery: 250 mAh lithium cell
- Expansion: HY2.0-4P Grove/Port A and Hat2-Bus
- Size/weight: `48.0 x 24.0 x 15.0 mm`, `20.0 g`

## Current Project Target

The repo already has a PlatformIO environment named `m5sticks3`:

```bash
pio run -e m5sticks3
pio run -e m5sticks3 -t upload
```

The project config matches the official ESP32-S3-PICO-1-N8R8, 8 MB flash, and 8 MB PSRAM spec. Upload uses native USB with `--before=no_reset`. The official download-mode instruction is to connect USB, long-press the side reset button, and wait for the internal green LED to blink.

## Library Integration Pattern

Normal application code should include only:

```cpp
#include <M5Unified.h>
```

Then initialize once:

```cpp
auto cfg = M5.config();
M5.begin(cfg);
M5.update();
```

M5Unified initializes the detected board, display, power manager, buttons, speaker, mic, RTC, and IMU according to `cfg`. For temporary local-library builds, prefer a non-committed PlatformIO override or `lib_extra_dirs = /Users/souler/Documents`; do not commit absolute user paths unless we intentionally pin this workspace.

## Display

M5GFX detects `board_M5StickS3` and configures an ST7789 panel:

- Logical size: `135 x 240`
- Official controller: `ST7789P3`
- Default portrait-friendly target for this repo: `M5.Display.setRotation(0)`
- SPI pins in local M5GFX: MOSI `GPIO39`, SCLK `GPIO40`, DC `GPIO45`, CS `GPIO41`, reset `GPIO21`
- Backlight PWM pin: `GPIO38`

Common calls:

```cpp
M5.Display.setBrightness(128);   // 0..255
M5.Display.sleep();
M5.Display.wakeup();
M5.Display.fillScreen(TFT_BLACK);
M5.Display.drawString("Hi", 67, 120);
```

For flicker-free UI, use `M5Canvas`:

```cpp
M5Canvas spr(&M5.Display);
spr.createSprite(135, 240);
spr.fillSprite(TFT_BLACK);
spr.pushSprite(0, 0);
```

## Buttons

Local M5Unified maps StickS3 GPIO buttons as:

- `M5.BtnA`: active-low `GPIO11`
- `M5.BtnB`: active-low `GPIO12`

This matches the official button map: `KEY1` on `GPIO11`, `KEY2` on `GPIO12`.

Use `M5.update()` every loop, then query:

```cpp
if (M5.BtnA.wasClicked()) {}
if (M5.BtnB.pressedFor(600)) {}
```

`M5.BtnPWR` should be treated carefully. This repo currently uses `M5.BtnPWR.wasClicked()` for screen-off toggling, but the local M5Unified StickS3 path maps the board to M5PM1 power management and does not clearly enable PMIC button events for `BtnPWR`. Verify on hardware before relying on app-level power-button clicks.

## IMU

M5Unified probes IMU devices and supports BMI270. For StickS3-class work, use the high-level API:

```cpp
float ax, ay, az;
float gx, gy, gz;
if (M5.Imu.isEnabled()) {
  M5.Imu.getAccel(&ax, &ay, &az);
  M5.Imu.getGyro(&gx, &gy, &gz);
}
```

The BMI270 conversion in local source uses +/-8 g for accel and +/-2000 dps for gyro. This is enough for shake, tilt, orientation, and gesture detection.

## Speaker

Official audio hardware is ES8311 over I2S with a MEMS microphone and AW8737 speaker amplifier. Official audio pins are:

- MCLK `GPIO18`
- DOUT `GPIO14`
- BCLK `GPIO17`
- LRCK `GPIO15`
- DIN `GPIO16`
- SCL `GPIO48`
- SDA `GPIO47`

Local M5Unified configures internal StickS3 speaker output as:

- MCLK `GPIO18`
- BCLK `GPIO17`
- LRCK/WS `GPIO15`
- DATA OUT `GPIO14`
- I2S port `I2S_NUM_0`
- Sample rate `44100`
- Stereo enabled

High-level usage:

```cpp
M5.Speaker.begin();
M5.Speaker.setVolume(128);       // 0..255
M5.Speaker.tone(1200, 80);
```

For WAV/raw playback, use `playWav()` or `playRaw()` from `M5.Speaker`. Keep sounds short for UI feedback unless we intentionally build an audio feature. Official docs recommend keeping speaker volume below 75% on battery power to avoid unexpected resets.

## Microphone

Official hardware includes a MEMS microphone through ES8311, with a listed SNR of 65 dB. However, the local StickS3 branch only shows internal speaker setup; it does not show an internal mic setup for `board_M5StickS3`. Treat microphone use as a library/configuration task until tested.

Generic mic pattern:

```cpp
M5.Speaker.end();     // mic and speaker often cannot run together
M5.Mic.begin();
int16_t samples[200];
M5.Mic.record(samples, 200, 16000);
```

## Power and Battery

M5Unified exposes:

```cpp
M5.Power.getBatteryLevel();
M5.Power.getBatteryVoltage();
M5.Power.isCharging();
M5.Power.setExtOutput(true);
M5.Power.powerOff();
M5.Power.deepSleep(usec);
M5.Power.lightSleep(usec);
```

Local source maps StickS3 to M5PM1 and implements external 5 V output through PMIC register bit control. Current project comments mention PY32 PMIC, so verify behavior on hardware before changing power-off, charging, or `BtnPWR` logic.

Official notes:

- `EXT_5V_EN` can switch the 5 V rail between input and output.
- `M5Unified` default initialization closes `EXT_5V_EN`, disabling Grove/Hat EXT_5V and IR TX/RX power unless external 5 V is supplied.
- Re-enable output mode with `M5.Power.setExtOutput(true)`.
- Do not feed power into output-mode 5 V interfaces except through USB or Hat2-Bus `5VIN`.

## I2C and External Expansion

Official and local maps agree:

- Internal I2C: SCL `GPIO48`, SDA `GPIO47`
- `BMI270`: I2C address `0x68`
- `M5PM1`: I2C address `0x6e`
- Port A / HY2.0-4P: black GND, red 5 V, yellow `GPIO9`, white `GPIO10`

Prefer M5Unified’s `M5.In_I2C` and `M5.Ex_I2C` wrappers instead of manually initializing Wire unless a device library requires it.

## IR

Official IR pins:

- IR TX: `GPIO46`
- IR RX: `GPIO42`

IR receive decoding must use the ESP32 RMT peripheral, not plain GPIO polling. Official docs also note that the speaker amplifier must be disabled for IR receive to work correctly.

## Implementation Checklist for Later Work

- Build with `pio run -e m5sticks3` before hardware testing.
- Confirm `M5.getBoard()` returns `board_M5StickS3`.
- Print and verify `M5.Display.width()` and `M5.Display.height()`.
- Test `BtnA`, `BtnB`, and `BtnPWR` separately with serial logs.
- Test `M5.Power.isCharging()` and battery voltage on USB and battery.
- Test `M5.Imu.isEnabled()` plus accel/gyro readings.
- Test speaker tone volume and whether it conflicts with BLE timing.
- Test microphone recording against the official ES8311/MEMS hardware.
- Test IR TX/RX with `M5.Power.setExtOutput(true)` and speaker amp disabled.
- Treat microphone, IR, and power-button behavior as hardware-confirmation items.
