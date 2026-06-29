#if defined(M5BUDDY_S3) || defined(BUDDY_BOARD_S3)
// M5StickS3 (ESP32-S3-PICO-1) impl — backed by M5Unified.
//
// Differences from M5StickC Plus that this file papers over:
//   • No AXP192 PMIC: power/battery come from M5.Power (unified API).
//   • No BM8563 RTC: time is kept entirely in software, seeded by the
//     bridge on every BLE connect (data.h sends {"time":[epoch,tz]}).
//   • Buzzer → speaker codec (M5.Speaker.tone has the same API shape).

#include "m5_compat.h"
#include <Arduino.h>
#include <time.h>

extern "C" uint8_t temprature_sens_read();   // legacy, may not exist on S3
#ifdef __cplusplus
extern "C" {
#endif
float temperatureRead();   // ESP32-S3 Arduino core internal SoC sensor
#ifdef __cplusplus
}
#endif

// ---- Power ----
float bdyBatV() {
  int mv = M5.Power.getBatteryVoltage();
  return (mv > 0) ? mv / 1000.0f : 0.0f;
}
float bdyBatI() {
  // M5StickS3's PMIC doesn't report charge current; the UI only shows
  // this as informational so 0 is a safe stand-in.
  return 0.0f;
}
float bdyVbusV() {
  // No direct VBUS ADC on the StickS3. Charge state is the proxy
  // main.cpp actually cares about (it just compares > 4.0f to detect
  // "on USB"). Report 5.0V while charging, 0 otherwise.
  return (M5.Power.isCharging() == m5::Power_Class::is_charging) ? 5.0f : 0.0f;
}
float bdyTempC() {
  // ESP32-S3 internal temperature sensor — far less useful than the
  // AXP192 die temp but at least non-zero for the diagnostics page.
  return temperatureRead();
}
void bdyScreenBreath(uint8_t pct) {
  if (pct > 100) pct = 100;
  M5.Display.setBrightness((uint8_t)((uint16_t)pct * 255 / 100));
}
void bdyDisplayPower(bool on) {
  if (on) M5.Display.wakeup();
  else    M5.Display.sleep();
}
void bdyPowerOff() {
  M5.Power.powerOff();
}
uint8_t bdyPwrBtnPress() {
  // Mirror the AXP192 GetBtnPress encoding the firmware already uses:
  //   0x02 = long press (>= ~1s), used to power off
  //   0x01 = short click
  //   0x00 = nothing
  if (M5.BtnPWR.wasHold())     return 0x02;
  if (M5.BtnPWR.wasClicked())  return 0x01;
  return 0x00;
}

// ---- IMU ----
void bdyImuInit() {
  M5.Imu.begin();
  // Plus's AXP192 reports a "long press" only after ~1.5s. M5Unified
  // defaults to a 500ms hold threshold, which makes a normal power-on
  // tap immediately fire bdyPwrBtnPress()==0x02 → main loop blanks the
  // screen. Stretch the threshold so brief boot taps don't trigger it.
  M5.BtnPWR.setHoldThresh(1500);
}
void bdyImuAccel(float* x, float* y, float* z) {
  float ax = 0, ay = 0, az = 0;
  M5.Imu.getAccel(&ax, &ay, &az);
  if (x) *x = ax; if (y) *y = ay; if (z) *z = az;
}

// ---- Speaker (replaces buzzer) ----
void bdyBeepInit() {
  M5.Speaker.begin();
  M5.Speaker.setVolume(64);   // ~25% — the codec is loud
}
void bdyBeep(uint16_t freq, uint16_t durMs) {
  M5.Speaker.tone(freq, durMs);
}
void bdyBeepUpdate() {
  // M5Unified runs the speaker on a background task; nothing to do.
}

// ---- Software RTC ----
// StickS3 has no battery-backed RTC. The bridge sends a time-sync the
// instant BLE pairs, so we just need a monotonic counter that survives
// reads at 1 Hz. epoch_at_set + (millis()-millis_at_set)/1000 is plenty
// accurate over a single power session.
static bool     _rtcSet = false;
static time_t   _epochAtSet = 0;
static uint32_t _millisAtSet = 0;

static time_t _currentEpoch() {
  if (!_rtcSet) return 0;
  uint32_t dt = (millis() - _millisAtSet) / 1000;
  return _epochAtSet + (time_t)dt;
}

static void _decompose(struct tm* out) {
  time_t e = _currentEpoch();
  gmtime_r(&e, out);
}

static time_t _composeEpoch(const struct tm* in) {
  // Treat the components as UTC so the round-trip is lossless. The
  // bridge already adjusted for the local TZ before handing the time
  // over (data.h: `local = epoch + tz_offset`).
  // newlib on ESP32 lacks timegm(), so compute days-since-epoch
  // directly using the proleptic Gregorian calendar.
  static const int mdays[] = {0,31,59,90,120,151,181,212,243,273,304,334};
  int year  = in->tm_year + 1900;
  int month = in->tm_mon;       // 0..11
  int day   = in->tm_mday;
  long days = (long)(year - 1970) * 365
            + (year - 1969) / 4
            - (year - 1901) / 100
            + (year - 1601) / 400
            + mdays[month]
            + day - 1;
  bool leap = ((year % 4 == 0) && (year % 100 != 0)) || (year % 400 == 0);
  if (leap && month >= 2) days++;
  return (time_t)(days * 86400L
                  + (long)in->tm_hour * 3600
                  + (long)in->tm_min  * 60
                  + (long)in->tm_sec);
}

// In-progress fields between SetDate/SetTime calls. The original code
// calls SetTime first and SetDate second; we accumulate and commit on
// each call so either order works.
static struct tm _staging = { 0, 0, 0, 1, 0, 100, 0, 0, 0 };  // 2000-01-01

void bdyRtcGetTime(RTC_TimeTypeDef* t) {
  if (!t) return;
  struct tm now;
  _decompose(&now);
  t->Hours   = (uint8_t)now.tm_hour;
  t->Minutes = (uint8_t)now.tm_min;
  t->Seconds = (uint8_t)now.tm_sec;
}

void bdyRtcGetDate(RTC_DateTypeDef* d) {
  if (!d) return;
  struct tm now;
  _decompose(&now);
  d->WeekDay = (uint8_t)now.tm_wday;
  d->Month   = (uint8_t)(now.tm_mon + 1);
  d->Date    = (uint8_t)now.tm_mday;
  d->Year    = (uint16_t)(now.tm_year + 1900);
}

void bdyRtcSetTime(const RTC_TimeTypeDef* t) {
  if (!t) return;
  _staging.tm_hour = t->Hours;
  _staging.tm_min  = t->Minutes;
  _staging.tm_sec  = t->Seconds;
  _epochAtSet  = _composeEpoch(&_staging);
  _millisAtSet = millis();
  _rtcSet = true;
}

void bdyRtcSetDate(const RTC_DateTypeDef* d) {
  if (!d) return;
  _staging.tm_wday = d->WeekDay;
  _staging.tm_mon  = (int)d->Month - 1;
  _staging.tm_mday = d->Date;
  _staging.tm_year = (int)d->Year - 1900;
  _epochAtSet  = _composeEpoch(&_staging);
  _millisAtSet = millis();
  _rtcSet = true;
}

#endif
