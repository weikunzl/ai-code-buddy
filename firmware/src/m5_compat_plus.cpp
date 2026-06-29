#if !defined(M5BUDDY_S3) && !defined(BUDDY_BOARD_S3)
// M5StickC Plus via M5Unified — keeps M5GFX fonts for UTF-8/CJK UI.

#include "m5_compat.h"

float bdyBatV() {
  int mv = M5.Power.getBatteryVoltage();
  return (mv > 0) ? mv / 1000.0f : 0.0f;
}
float bdyBatI() {
  return M5.Power.getBatteryCurrent();
}
float bdyVbusV() {
  int mv = M5.Power.getVBUSVoltage();
  return (mv > 0) ? mv / 1000.0f : 0.0f;
}
float bdyTempC() {
  return 0.0f;   // no AXP192 die temp via M5Unified on Plus
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
  if (M5.BtnPWR.wasClicked()) return 0x02;
  return 0x00;
}

void bdyImuInit() {
  M5.Imu.begin();
}
void bdyImuAccel(float* x, float* y, float* z) {
  float ax = 0, ay = 0, az = 0;
  M5.Imu.getAccelData(&ax, &ay, &az);
  if (x) *x = ax; if (y) *y = ay; if (z) *z = az;
}

void bdyBeepInit() {
  M5.Speaker.begin();
  M5.Speaker.setVolume(255);
}
void bdyBeep(uint16_t freq, uint16_t durMs) {
  M5.Speaker.tone(freq, durMs);
}
void bdyBeepUpdate() {
  // M5Unified speaker runs on a background task.
}

void bdyRtcGetTime(RTC_TimeTypeDef* t) {
  if (!t) return;
  m5::rtc_time_t tm;
  if (M5.Rtc.getTime(&tm)) {
    t->Hours   = (uint8_t)tm.hours;
    t->Minutes = (uint8_t)tm.minutes;
    t->Seconds = (uint8_t)tm.seconds;
  }
}
void bdyRtcGetDate(RTC_DateTypeDef* d) {
  if (!d) return;
  m5::rtc_date_t dt;
  if (M5.Rtc.getDate(&dt)) {
    d->WeekDay = (uint8_t)dt.weekDay;
    d->Month   = (uint8_t)dt.month;
    d->Date    = (uint8_t)dt.date;
    d->Year    = (uint16_t)dt.year;
  }
}
void bdyRtcSetTime(const RTC_TimeTypeDef* t) {
  if (!t) return;
  m5::rtc_time_t tm;
  tm.hours = t->Hours; tm.minutes = t->Minutes; tm.seconds = t->Seconds;
  M5.Rtc.setTime(&tm);
}
void bdyRtcSetDate(const RTC_DateTypeDef* d) {
  if (!d) return;
  m5::rtc_date_t dt;
  dt.weekDay = d->WeekDay; dt.month = d->Month; dt.date = d->Date; dt.year = d->Year;
  M5.Rtc.setDate(&dt);
}

#endif
