#pragma once

// Platform abstraction. The firmware was originally written for the
// M5StickC Plus (ESP32, M5StickCPlus library). The M5StickS3 (ESP32-S3,
// successor to Plus2) needs M5Unified — different chip family and a
// different driver surface. This header pulls in the right base library
// and exposes a small set of `bdy*()` helpers so the rest of the source
// stays platform-agnostic.

#if defined(M5BUDDY_S3) || defined(BUDDY_BOARD_S3)
  #include <M5Unified.h>
  #include <Arduino.h>
  // M5Unified ships M5GFX whose drawing surfaces derive from
  // `LovyanGFX`. The codebase was written against TFT_eSPI; both
  // libraries expose nearly identical drawing APIs (drawString,
  // setTextColor, fillRect…), so aliases at the type level get most
  // of the source compiling unchanged. The base class TFT_eSPI is
  // used as a polymorphic render target (sprite or Lcd), which is
  // exactly the role LovyanGFX plays in M5GFX.
  using TFT_eSPI    = LovyanGFX;
  using TFT_eSprite = LGFX_Sprite;

  // M5StickCPlus's RTC types — recreated here so existing struct-field
  // access (.Hours/.Minutes/.WeekDay/.Month/.Date) keeps compiling.
  // M5StickS3 has no hardware RTC; bdyRtc*() backs these with a software
  // clock that the bridge re-syncs on every BLE connect (data.h).
  struct RTC_TimeTypeDef { uint8_t Hours; uint8_t Minutes; uint8_t Seconds; };
  struct RTC_DateTypeDef { uint8_t WeekDay; uint8_t Month; uint8_t Date; uint16_t Year; };
#else
  #include <M5Unified.h>
  #include <Arduino.h>
  using TFT_eSPI    = LovyanGFX;
  using TFT_eSprite = LGFX_Sprite;
  struct RTC_TimeTypeDef { uint8_t Hours; uint8_t Minutes; uint8_t Seconds; };
  struct RTC_DateTypeDef { uint8_t WeekDay; uint8_t Month; uint8_t Date; uint16_t Year; };
#endif

// ---- Power / charge ----
float    bdyBatV();          // battery voltage, volts
float    bdyBatI();          // battery current, mA (positive = charging)
float    bdyVbusV();         // VBUS voltage, volts
float    bdyTempC();         // PMIC die temperature, °C (chip-internal on S3)
void     bdyScreenBreath(uint8_t pct);   // 0..100 → display backlight
void     bdyDisplayPower(bool on);       // sleep/wake the LCD backlight rail
void     bdyPowerOff();                  // power down (or deep-sleep on S3)
uint8_t  bdyPwrBtnPress();               // 0=none, 1=short, 2=long (matches AXP192 encoding)

// ---- IMU ----
void     bdyImuInit();
void     bdyImuAccel(float* x, float* y, float* z);  // g

// ---- Buzzer / speaker ----
void     bdyBeepInit();
void     bdyBeep(uint16_t freq, uint16_t durMs);
void     bdyBeepUpdate();

// ---- RTC (software-backed on S3) ----
void     bdyRtcGetTime(RTC_TimeTypeDef* t);
void     bdyRtcGetDate(RTC_DateTypeDef* d);
void     bdyRtcSetTime(const RTC_TimeTypeDef* t);
void     bdyRtcSetDate(const RTC_DateTypeDef* d);
