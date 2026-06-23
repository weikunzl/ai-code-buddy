#include <M5Unified.h>
#include <LittleFS.h>
#include <mbedtls/base64.h>
#include <stdarg.h>
#include "ble_bridge.h"
#include "data.h"
#include "buddy.h"
#include "wav_assets.h"

M5Canvas spr = M5Canvas(&M5.Lcd);

// Advertise as "Claude-XXXX" (last two BT MAC bytes) so multiple sticks
// in one room are distinguishable in the desktop picker. Name persists in
// btName for the BLUETOOTH info page.
static char btName[16] = "Claude";
static void startBt() {
  uint8_t mac[6] = {0};
  esp_read_mac(mac, ESP_MAC_BT);
  snprintf(btName, sizeof(btName), "Claude-%02X%02X", mac[4], mac[5]);
  bleInit(btName);
}

#include "character.h"
#include "stats.h"
const int W = 135, H = 240;
const int CX = W / 2;
const int CY_BASE = 120;
#ifndef BUDDY_BOARD_S3
// Original StickC Plus has a red LED on GPIO 10 (active-low). StickS3
// doesn't have this LED at all — attention is indicated by a red border
// drawn into the sprite instead (see alertBorderActive below).
const int LED_PIN = 10;
#endif

// Colors used across multiple UI surfaces
const uint16_t HOT   = 0xFA20;   // red-orange: warnings, impatience, deny
const uint16_t PANEL = 0x2104;   // overlay panel background

enum PersonaState { P_SLEEP, P_IDLE, P_BUSY, P_ATTENTION, P_CELEBRATE, P_DIZZY, P_HEART };
const char* stateNames[] = { "sleep", "idle", "busy", "attention", "celebrate", "dizzy", "heart" };

TamaState    tama;
PersonaState baseState   = P_SLEEP;
PersonaState activeState = P_SLEEP;
uint32_t     oneShotUntil = 0;
uint32_t     lastShakeCheck = 0;
float        accelBaseline = 1.0f;
unsigned long t = 0;

// Menu
bool    menuOpen    = false;
uint8_t menuSel     = 0;
uint8_t brightLevel = 4;           // 0..4 → ScreenBreath 20..100
bool    btnALong    = false;
bool    btnBLong    = false;

enum DisplayMode { DISP_NORMAL, DISP_SESSION, DISP_SESSIONS, DISP_PET, DISP_INFO, DISP_COUNT };
uint8_t displayMode = DISP_NORMAL;
uint8_t infoPage = 0;
uint8_t petPage = 0;
const uint8_t PET_PAGES = 2;
uint8_t msgScroll = 0;
uint8_t sessionPage = 0;
uint16_t lastLineGen = 0;
uint16_t lastPendingGen = 0;
uint16_t lastEventGen = 0;
char     lastPromptId[40] = "";
uint32_t lastInteractMs = 0;
bool     dimmed = false;
bool     screenOff = false;
// StickS3 has no physical LED; when attention is pending we pulse a red
// border around the sprite edge instead. Unused on the classic StickC
// Plus but harmless to leave defined.
bool     alertBorderActive = false;
bool     swallowBtnA = false;
bool     swallowBtnB = false;
bool     buddyMode = false;
bool     gifAvailable = false;
const uint8_t SPECIES_GIF = 0xFF;   // species NVS sentinel: use the installed GIF

// Cycle GIF (if installed) → ASCII species 0..N-1 → GIF. Persisted to the
// existing "species" NVS key; 0xFF means GIF mode.
static void nextPet() {
  uint8_t n = buddySpeciesCount();
  if (!buddyMode) {                          // GIF → species 0
    buddyMode = true;
    buddySetSpeciesIdx(0);
    speciesIdxSave(0);
  } else if (buddySpeciesIdx() + 1 >= n && gifAvailable) {  // last species → GIF
    buddyMode = false;
    speciesIdxSave(SPECIES_GIF);
  } else {                                   // species i → species i+1
    buddyNextSpecies();
  }
  characterInvalidate();
  if (buddyMode) buddyInvalidate();
}
uint32_t wakeTransitionUntil = 0;
const uint32_t SCREEN_OFF_MS = 30000;

bool     napping = false;
uint32_t napStartMs = 0;
uint32_t promptArrivedMs = 0;
bool     micRecording = false;
char     micAudioId[24] = "";
char     micAudioSid[24] = "";
char     micDecisionId[40] = "";
uint32_t micStartedMs = 0;
uint16_t micChunkSeq = 0;
uint32_t micBytesSent = 0;
static constexpr uint32_t MIC_SAMPLE_RATE = 8000;
static constexpr uint16_t MIC_CHUNK_BYTES = 512;
static constexpr uint32_t MIC_MAX_MS = 10000;
static uint8_t micChunkBuf[MIC_CHUNK_BYTES];

// Face-down = Z-axis dominant and negative. Debounced so a toss doesn't count.
static bool isFaceDown() {
  float ax, ay, az;
  M5.Imu.getAccelData(&ax, &ay, &az);
  return az < -0.7f && fabsf(ax) < 0.4f && fabsf(ay) < 0.4f;
}

// Old AXP ScreenBreath was 0..100; M5Unified Display brightness is 0..255.
// 5 levels (0..4) → ~51..255.
static void applyBrightness() { M5.Display.setBrightness(51 + brightLevel * 51); }

static void wake() {
  lastInteractMs = millis();
  if (screenOff) {
    M5.Display.wakeup();
    applyBrightness();
    screenOff = false;
    wakeTransitionUntil = millis() + 12000;
  }
  if (dimmed) { applyBrightness(); dimmed = false; }
}
bool     responseSent = false;
uint32_t responseSentMs = 0;
// If the host never clears a prompt we already answered (it timed out, or the
// link dropped), don't get stuck forever with the buttons ignored — locally
// dismiss the prompt and return to normal after this grace period.
const uint32_t PROMPT_CLEAR_TIMEOUT_MS = 6000;

static void beep(uint16_t freq, uint16_t dur) {
  if (settings().sound) M5.Speaker.tone(freq, dur);
}

static bool waitForSpeakerStart(uint32_t timeoutMs) {
  uint32_t start = millis();
  while ((uint32_t)(millis() - start) < timeoutMs) {
    if (M5.Speaker.isPlaying()) return true;
    delay(1);
  }
  return M5.Speaker.isPlaying();
}

static void toneInputRequired() {
  if (!settings().sound) return;
  bool played = M5.Speaker.playRaw(kInputRequiredPcm, kInputRequiredPcmSamples, kInputRequiredPcmSampleRate, false, 1, 0, true);
  if (!played || !waitForSpeakerStart(30)) beep(1200, 80);
}

static void toneUiClick() {
  if (!settings().sound) return;
  bool played = M5.Speaker.playRaw(kUiClickPcm, kUiClickPcmSamples, kUiClickPcmSampleRate, false, 1, 0, true);
  if (!played || !waitForSpeakerStart(30)) beep(1800, 30);
}

static void toneAnswerSent() {
  if (!settings().sound) return;
  bool played = M5.Speaker.playRaw(kAnswerSentPcm, kAnswerSentPcmSamples, kAnswerSentPcmSampleRate, false, 1, 0, true);
  if (!played || !waitForSpeakerStart(30)) beep(2400, 60);
}

static void toneDenied() {
  beep(600, 60);
}

static void toneWarning() {
  beep(1400, 60);
}

static void toneComplete() {
  if (!settings().sound) return;
  bool played = M5.Speaker.playRaw(kCompletePcm, kCompletePcmSamples, kCompletePcmSampleRate, false, 1, 0, true);
  if (!played || !waitForSpeakerStart(30)) {
    beep(1600, 60);
    delay(80);
    beep(2200, 60);
  }
}

static void toneFocusAck() {
  toneUiClick();
}

static void toneEventError() {
  beep(500, 120);
}

static void toneEventNeutral() {
  beep(1000, 60);
}

static void toneResetConfirm() {
  beep(800, 200);
}

static void tonePairing() {
  beep(1800, 60);
}

static void sendCmd(const char* json) {
  Serial.println(json);
  size_t n = strlen(json);
  bleWrite((const uint8_t*)json, n);
  bleWrite((const uint8_t*)"\n", 1);
}

static void sendPermissionDecision(const char* id, const char* decision) {
  char cmd[128];
  snprintf(cmd, sizeof(cmd), "{\"cmd\":\"permission\",\"id\":\"%s\",\"decision\":\"%s\"}", id, decision);
  sendCmd(cmd);
}

static void sendAnswerChoice(const char* id, const char* choice) {
  char cmd[144];
  snprintf(cmd, sizeof(cmd), "{\"cmd\":\"answer\",\"id\":\"%s\",\"choice\":\"%s\"}", id, choice);
  sendCmd(cmd);
}

static uint8_t multiChoiceCount(const PendingDecision& d) {
  uint8_t n = 0;
  for (uint8_t i = 0; i < d.nOptions; i++) {
    if (d.options[i].selected) n++;
  }
  return n;
}

static void sendAnswerChoices(const PendingDecision& d) {
  char cmd[256];
  size_t used = snprintf(cmd, sizeof(cmd), "{\"cmd\":\"answer\",\"id\":\"%s\",\"choices\":[", d.id);
  bool first = true;
  for (uint8_t i = 0; i < d.nOptions && used < sizeof(cmd); i++) {
    if (!d.options[i].selected) continue;
    used += snprintf(cmd + used, sizeof(cmd) - used, "%s\"%s\"", first ? "" : ",", d.options[i].id);
    first = false;
  }
  if (used < sizeof(cmd)) snprintf(cmd + used, sizeof(cmd) - used, "]}");
  sendCmd(cmd);
}

static void sendFocusSession(const char* sid) {
  char cmd[96];
  snprintf(cmd, sizeof(cmd), "{\"cmd\":\"focus\",\"sid\":\"%s\"}", sid);
  sendCmd(cmd);
}

extern bool settingsOpen;
extern bool resetOpen;

static void restoreSpeaker() {
  M5.Speaker.begin();
  M5.Speaker.setVolume(255);
  M5.Speaker.setAllChannelVolume(255);
}

static void resetMicState() {
  micRecording = false;
  micAudioId[0] = 0;
  micAudioSid[0] = 0;
  micDecisionId[0] = 0;
  micStartedMs = 0;
  micChunkSeq = 0;
  micBytesSent = 0;
}

static bool resolveMicTarget(char* sid, size_t sidSize, char* decisionId, size_t decisionSize) {
  if (!sid || sidSize == 0 || !decisionId || decisionSize == 0) return false;
  sid[0] = 0;
  decisionId[0] = 0;
  if (tama.nPending > 0) {
    if (tama.pending[0].sid[0]) _copyField(sid, sidSize, tama.pending[0].sid);
    if (tama.pending[0].id[0]) _copyField(decisionId, decisionSize, tama.pending[0].id);
  }
  if (!sid[0] && tama.focused[0]) _copyField(sid, sidSize, tama.focused);
  if (!sid[0]) {
    for (uint8_t i = 0; i < tama.nSessions; i++) {
      if (tama.sessions[i].focused && tama.sessions[i].sid[0]) {
        _copyField(sid, sidSize, tama.sessions[i].sid);
        break;
      }
    }
  }
  if (!sid[0] && tama.nSessions > 0 && tama.sessions[0].sid[0]) {
    _copyField(sid, sidSize, tama.sessions[0].sid);
  }
  return sid[0] != 0;
}

static bool micStartRecording() {
#ifdef BUDDY_BOARD_S3
  if (micRecording || screenOff || menuOpen || settingsOpen || resetOpen) return false;
  char sid[24];
  char decisionId[40];
  if (!resolveMicTarget(sid, sizeof(sid), decisionId, sizeof(decisionId))) return false;
  snprintf(micAudioId, sizeof(micAudioId), "mic_%lu", (unsigned long)millis());
  _copyField(micAudioSid, sizeof(micAudioSid), sid);
  _copyField(micDecisionId, sizeof(micDecisionId), decisionId);
  micChunkSeq = 0;
  micBytesSent = 0;
  micStartedMs = millis();
  M5.Speaker.stop();
  M5.Speaker.end();
  if (!M5.Mic.begin()) {
    restoreSpeaker();
    resetMicState();
    toneDenied();
    return false;
  }
  char cmd[192];
  snprintf(
      cmd, sizeof(cmd),
      "{\"cmd\":\"audio_begin\",\"id\":\"%s\",\"sid\":\"%s\",\"decision_id\":\"%s\","
      "\"format\":\"pcm_u8\",\"sample_rate\":%lu,\"channels\":1,\"bits\":8}",
      micAudioId, micAudioSid, micDecisionId, (unsigned long)MIC_SAMPLE_RATE);
  sendCmd(cmd);
  micRecording = true;
  wake();
  return true;
#else
  return false;
#endif
}

static bool micCaptureAndSendChunk() {
#ifdef BUDDY_BOARD_S3
  if (!micRecording) return false;
  if (!M5.Mic.record(micChunkBuf, MIC_CHUNK_BYTES, MIC_SAMPLE_RATE, false)) return false;
  uint32_t start = millis();
  while (M5.Mic.isRecording()) {
    M5.update();
    delay(1);
    if ((uint32_t)(millis() - start) > 1000) return false;
  }
  char b64[((MIC_CHUNK_BYTES + 2) / 3) * 4 + 4];
  size_t outLen = 0;
  int rc = mbedtls_base64_encode(
      (unsigned char*)b64, sizeof(b64), &outLen, micChunkBuf, MIC_CHUNK_BYTES);
  if (rc != 0 || outLen == 0 || outLen >= sizeof(b64)) return false;
  b64[outLen] = 0;
  char cmd[960];
  snprintf(
      cmd, sizeof(cmd),
      "{\"cmd\":\"audio_chunk\",\"id\":\"%s\",\"seq\":%u,\"data\":\"%s\"}",
      micAudioId, micChunkSeq, b64);
  sendCmd(cmd);
  micChunkSeq++;
  micBytesSent += MIC_CHUNK_BYTES;
  lastInteractMs = millis();
  return true;
#else
  return false;
#endif
}

static void micStopRecording(bool cancel) {
#ifdef BUDDY_BOARD_S3
  if (!micAudioId[0] && !micRecording) return;
  bool hadData = micChunkSeq > 0;
  char aid[24];
  _copyField(aid, sizeof(aid), micAudioId);
  if (M5.Mic.isEnabled()) {
    while (M5.Mic.isRecording()) delay(1);
    M5.Mic.end();
  }
  restoreSpeaker();
  resetMicState();
  if (aid[0]) {
    char cmd[96];
    snprintf(
        cmd, sizeof(cmd),
        "{\"cmd\":\"%s\",\"id\":\"%s\"}",
        (cancel || !hadData) ? "audio_cancel" : "audio_end", aid);
    sendCmd(cmd);
  }
  if (cancel || !hadData) toneDenied();
  else toneAnswerSent();
#endif
}

static void micTick() {
  if (!micRecording) return;
  if ((uint32_t)(millis() - micStartedMs) >= MIC_MAX_MS) {
    micStopRecording(false);
    return;
  }
  if (!micCaptureAndSendChunk()) micStopRecording(true);
}

const uint8_t INFO_PAGES = 6;
const uint8_t INFO_PG_BUTTONS = 1;
const uint8_t INFO_PG_CREDITS = 5;

static bool shouldPeekCompanion() {
  return displayMode != DISP_NORMAL || tama.promptId[0] || tama.nPending > 0;
}

static void syncCompanionPeek() {
  bool peek = shouldPeekCompanion();
  characterSetPeek(peek);
  buddySetPeek(peek);
}

void applyDisplayMode() {
  syncCompanionPeek();
  // Clear the whole sprite on mode switch. drawInfo/drawPet clear their
  // own regions when they run, but when you switch FROM info/pet TO normal,
  // those functions stop running and their stale pixels stay behind. Full
  // clear is cheap and guarantees no leftovers between modes.
  spr.fillSprite(0x0000);
  characterInvalidate();  // redraws character on next tick (text mode path)
}

const char* menuItems[] = { "settings", "turn off", "help", "about", "demo", "close" };
const uint8_t MENU_N = 6;

bool    settingsOpen = false;
uint8_t settingsSel  = 0;
const char* settingsItems[] = { "brightness", "sound", "bluetooth", "wifi", "led", "transcript", "clock rot", "ascii pet", "reset", "back" };
const uint8_t SETTINGS_N = 10;

bool    resetOpen = false;
uint8_t resetSel  = 0;
const char* resetItems[] = { "delete char", "factory reset", "back" };
const uint8_t RESET_N = 3;
static uint32_t resetConfirmUntil = 0;
static uint8_t  resetConfirmIdx = 0xFF;

static void applySetting(uint8_t idx) {
  Settings& s = settings();
  switch (idx) {
    case 0:
      brightLevel = (brightLevel + 1) % 5;
      applyBrightness();
      return;
    case 1: s.sound = !s.sound; break;
    case 2:
      // BT toggle is a stored preference only — BLE stays live. Turning
      // BLE off cleanly would require tearing down the BLE stack which
      // the Arduino BLE library doesn't do reliably. If we need a
      // hard-off someday, stop advertising via BLEDevice::getAdvertising().
      s.bt = !s.bt;
      break;
    case 3: s.wifi = !s.wifi; break;   // stored only — no WiFi stack linked
    case 4: s.led = !s.led; break;
    case 5: s.hud = !s.hud; break;
    case 6: s.clockRot = (s.clockRot + 1) % 3; break;
    case 7: nextPet(); return;
    case 8: resetOpen = true; resetSel = 0; resetConfirmIdx = 0xFF; return;
    case 9: settingsOpen = false; characterInvalidate(); return;
  }
  settingsSave();
}

// Tap-twice confirm: first tap arms (label flips to "really?"), second
// within 3s executes. Scrolling away clears the arm.
static void applyReset(uint8_t idx) {
  uint32_t now = millis();
  bool armed = (resetConfirmIdx == idx) && (int32_t)(now - resetConfirmUntil) < 0;

  if (idx == 2) { resetOpen = false; return; }

  if (!armed) {
    resetConfirmIdx = idx;
    resetConfirmUntil = now + 3000;
    toneWarning();
    return;
  }

  toneResetConfirm();
  if (idx == 0) {
    // delete char: wipe /characters/, reboot into ASCII mode
    File d = LittleFS.open("/characters");
    if (d && d.isDirectory()) {
      File e;
      while ((e = d.openNextFile())) {
        char path[80];
        snprintf(path, sizeof(path), "/characters/%s", e.name());
        if (e.isDirectory()) {
          File f;
          while ((f = e.openNextFile())) {
            char fp[128];
            snprintf(fp, sizeof(fp), "%s/%s", path, f.name());
            f.close();
            LittleFS.remove(fp);
          }
          e.close();
          LittleFS.rmdir(path);
        } else {
          e.close();
          LittleFS.remove(path);
        }
      }
      d.close();
    }
  } else {
    // factory reset: NVS namespace wipe + filesystem format + BLE bonds.
    // Clears stats, owner, petname, species, settings, GIF characters,
    // and any stored LTKs so the next desktop has to re-pair.
    _prefs.begin("buddy", false);
    _prefs.clear();
    _prefs.end();
    LittleFS.format();
    bleClearBonds();
  }
  delay(300);
  ESP.restart();
}

// Footer hint row inside a menu panel: "<downLbl> ↓  <rightLbl> →" with
// pixel triangles. Panels add MENU_HINT_H to height and call this at bottom.
const int MENU_HINT_H = 14;
static void drawMenuHints(const Palette& p, int mx, int mw, int hy,
                          const char* downLbl = "A", const char* rightLbl = "B") {
  spr.drawFastHLine(mx + 6, hy - 4, mw - 12, p.textDim);
  spr.setTextColor(p.textDim, PANEL);
  // 6px/glyph at size 1; triangle goes 4px after the label ends
  int x = mx + 8;
  spr.setCursor(x, hy); spr.print(downLbl);
  x += strlen(downLbl) * 6 + 4;
  spr.fillTriangle(x, hy + 1, x + 6, hy + 1, x + 3, hy + 6, p.textDim);
  x = mx + mw / 2 + 4;
  spr.setCursor(x, hy); spr.print(rightLbl);
  x += strlen(rightLbl) * 6 + 4;
  spr.fillTriangle(x, hy, x, hy + 6, x + 5, hy + 3, p.textDim);
}

static void drawSettings() {
  const Palette& p = characterPalette();
  int mw = 118, mh = 16 + SETTINGS_N * 14 + MENU_HINT_H;
  int mx = (W - mw) / 2, my = (H - mh) / 2;
  spr.fillRoundRect(mx, my, mw, mh, 4, PANEL);
  spr.drawRoundRect(mx, my, mw, mh, 4, p.textDim);
  spr.setTextSize(1);
  Settings& s = settings();
  bool vals[] = { s.sound, s.bt, s.wifi, s.led, s.hud };
  for (int i = 0; i < SETTINGS_N; i++) {
    bool sel = (i == settingsSel);
    spr.setTextColor(sel ? p.text : p.textDim, PANEL);
    spr.setCursor(mx + 6, my + 8 + i * 14);
    spr.print(sel ? "> " : "  ");
    spr.print(settingsItems[i]);
    spr.setCursor(mx + mw - 36, my + 8 + i * 14);
    spr.setTextColor(p.textDim, PANEL);
    if (i == 0) {
      spr.printf("%u/4", brightLevel);
    } else if (i >= 1 && i <= 5) {
      spr.setTextColor(vals[i-1] ? GREEN : p.textDim, PANEL);
      spr.print(vals[i-1] ? " on" : "off");
    } else if (i == 6) {
      static const char* const RN[] = { "auto", "port", "land" };
      spr.print(RN[s.clockRot]);
    } else if (i == 7) {
      uint8_t total = buddySpeciesCount() + (gifAvailable ? 1 : 0);
      uint8_t pos   = buddyMode ? buddySpeciesIdx() + 1 : total;
      spr.printf("%u/%u", pos, total);
    }
  }
  drawMenuHints(p, mx, mw, my + mh - 12, "Next", "Change");
}

static void drawReset() {
  const Palette& p = characterPalette();
  int mw = 118, mh = 16 + RESET_N * 14 + MENU_HINT_H;
  int mx = (W - mw) / 2, my = (H - mh) / 2;
  spr.fillRoundRect(mx, my, mw, mh, 4, PANEL);
  spr.drawRoundRect(mx, my, mw, mh, 4, HOT);
  spr.setTextSize(1);
  for (int i = 0; i < RESET_N; i++) {
    bool sel = (i == resetSel);
    spr.setTextColor(sel ? p.text : p.textDim, PANEL);
    spr.setCursor(mx + 6, my + 8 + i * 14);
    spr.print(sel ? "> " : "  ");
    bool armed = (i == resetConfirmIdx) &&
                 (int32_t)(millis() - resetConfirmUntil) < 0;
    if (armed) spr.setTextColor(HOT, PANEL);
    spr.print(armed ? "really?" : resetItems[i]);
  }
  drawMenuHints(p, mx, mw, my + mh - 12);
}

void menuConfirm() {
  switch (menuSel) {
    case 0: settingsOpen = true; menuOpen = false; settingsSel = 0; break;
    case 1: M5.Power.powerOff(); break;
    case 2:
    case 3:
      menuOpen = false;
      displayMode = DISP_INFO;
      infoPage = (menuSel == 2) ? INFO_PG_BUTTONS : INFO_PG_CREDITS;
      applyDisplayMode();
      characterInvalidate();
      break;
    case 4: dataSetDemo(!dataDemo()); break;
    case 5: menuOpen = false; characterInvalidate(); break;
  }
}

void drawMenu() {
  const Palette& p = characterPalette();
  int mw = 118, mh = 16 + MENU_N * 14 + MENU_HINT_H;
  int mx = (W - mw) / 2, my = (H - mh) / 2;
  spr.fillRoundRect(mx, my, mw, mh, 4, PANEL);
  spr.drawRoundRect(mx, my, mw, mh, 4, p.textDim);
  spr.setTextSize(1);
  for (int i = 0; i < MENU_N; i++) {
    bool sel = (i == menuSel);
    spr.setTextColor(sel ? p.text : p.textDim, PANEL);
    spr.setCursor(mx + 6, my + 8 + i * 14);
    spr.print(sel ? "> " : "  ");
    spr.print(menuItems[i]);
    if (i == 4) spr.print(dataDemo() ? "  on" : "  off");
  }
  drawMenuHints(p, mx, mw, my + mh - 12);
}

// Clock orientation: gravity along the in-plane X axis means the stick is
// on its side. Signed counter for hysteresis on both transitions — same
// pattern as face-down nap.
//   0 = portrait (sprite path, pet sleeps underneath)
//   1 = landscape, BtnA-side down (M5.Lcd rotation 1)
//   3 = landscape, USB-side down (M5.Lcd rotation 3)
static uint8_t clockOrient   = 0;
static int8_t  orientFrames  = 0;
static uint8_t paintedOrient = 0;
// RTC and IMU share an I2C bus. Reading the RTC at 60fps starves the IMU
// reads in clockUpdateOrient — orientation detection gets noisy. Cache the
// time once per second; mood logic and drawClock both read from here.
static m5::rtc_time_t _clkTm;
static m5::rtc_date_t _clkDt;
uint32_t              _clkLastRead = 0;   // zeroed by data.h on time-sync
static bool           _onUsb       = false;
// True only if the last getTime/getDate actually read from RTC hardware.
// StickS3 has no external RTC chip, so these return false and leave the
// structs at their default (-1) values; without this check, the clock
// face tries to format -1 as %02u and renders garbage like "42949".
static bool           _clkHwOk     = false;
static void clockRefreshRtc() {
  if (millis() - _clkLastRead < 1000) return;
  _clkLastRead = millis();
  // getVBUSVoltage returns mV (-1 if unsupported). Threshold at 4000mV.
  _onUsb = M5.Power.getVBUSVoltage() > 4000;
  _clkHwOk = M5.Rtc.getTime(&_clkTm) && M5.Rtc.getDate(&_clkDt);
}

static void clockUpdateOrient() {
  float ax, ay, az;
  M5.Imu.getAccelData(&ax, &ay, &az);
  uint8_t lock = settings().clockRot;
  if (lock == 1) { clockOrient = 0; return; }
  if (lock == 2) {
    // Locked landscape: never drop to 0, but still pick 1 vs 3 from
    // gravity so the cradle works either way up. Need a strong tilt
    // for the 1↔3 swap so handling jitter doesn't flip it; otherwise
    // hold whatever we last had (or 1 from boot).
    if (clockOrient == 0) clockOrient = (ax >= 0) ? 1 : 3;
    if      (ax >  0.5f && clockOrient != 1) clockOrient = 1;
    else if (ax < -0.5f && clockOrient != 3) clockOrient = 3;
    return;
  }
  // Dual threshold: strict to enter (must be clearly sideways), loose to
  // stay (tolerate ~65° of tilt). With one shared threshold a slight lean
  // while sitting on the long edge puts ax right at the boundary and the
  // counter ratchets down in ~half a second.
  bool side = (clockOrient == 0)
    ? fabsf(ax) > 0.7f && fabsf(ay) < 0.5f && fabsf(az) < 0.5f
    : fabsf(ax) > 0.4f;
  if (side) { if (orientFrames < 20) orientFrames++; }
  else      { if (orientFrames > -10) orientFrames--; }
  if (clockOrient == 0 && orientFrames >= 15) {
    clockOrient = (ax > 0) ? 1 : 3;
  } else if (clockOrient != 0 && orientFrames <= -8) {
    clockOrient = 0;
  } else if (clockOrient != 0 && side) {
    // Direct 1↔3: a fast flip keeps |ax|>0.7 (just changes sign), so
    // `side` never drops and the exit-via-0 path can't fire. Watch for
    // ax sign disagreeing with the stored orientation.
    static int8_t swapFrames = 0;
    uint8_t want = (ax > 0) ? 1 : 3;
    if (want != clockOrient) { if (++swapFrames >= 8) { clockOrient = want; swapFrames = 0; } }
    else swapFrames = 0;
  }
}

// Clock face: shown when charging on USB with nothing else going on.
// Portrait paints the upper ~110px to the sprite; pet renders below.
// Landscape draws direct to LCD with rotation — sprite stays untouched.
static const char* const MON[] = {
  "Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"
};
static const char* const DOW[] = {"Sun","Mon","Tue","Wed","Thu","Fri","Sat"};

static uint8_t clockDow() { return _clkDt.weekDay % 7; }
static void drawClock() {
  const Palette& p = characterPalette();
  // RTC fields are int8_t and default to -1 when unset. %02d keeps the
  // formatter signed, so a stray -1 prints "-1" instead of UINT32_MAX
  // truncated to the buffer (which was the "42949" garbage bug).
  char hm[6]; snprintf(hm, sizeof(hm), "%02d:%02d", _clkTm.hours, _clkTm.minutes);
  char ss[4]; snprintf(ss, sizeof(ss), ":%02d", _clkTm.seconds);
  uint8_t mi = (_clkDt.month >= 1 && _clkDt.month <= 12) ? _clkDt.month - 1 : 0;
  char dl[8]; snprintf(dl, sizeof(dl), "%s %02d", MON[mi], _clkDt.date);

  if (clockOrient == 0) {
    paintedOrient = 0;
    // Bottom half — buddy naturally lives at y=0..82, GIF peeks at top
    // via peek mode. Clearing from 90 leaves both untouched.
    spr.fillRect(0, 90, W, H - 90, p.bg);
    spr.setTextDatum(MC_DATUM);
    spr.setTextSize(4); spr.setTextColor(p.text, p.bg);    spr.drawString(hm, CX, 140);
    spr.setTextSize(2); spr.setTextColor(p.textDim, p.bg); spr.drawString(ss, CX, 175);
    spr.setTextSize(1);                                     spr.drawString(dl, CX, 200);
    spr.setTextDatum(TL_DATUM);
    return;
  }

  // Landscape: 240×135 direct-to-LCD. Full fill only on entry; after that
  // text glyph bg cells repaint themselves and the pet box (small, ~90×50)
  // gets a fillRect each pet tick — small enough not to tear.
  M5.Lcd.setRotation(clockOrient);
  static uint8_t lastSec = 0xFF;
  bool repaint = paintedOrient != clockOrient;
  if (repaint) { M5.Lcd.fillScreen(p.bg); paintedOrient = clockOrient; lastSec = 0xFF; }

  // Seconds tick at 1Hz; redrawing 3 strings at 60fps is 180 SPI ops/sec
  // for nothing. Gate on the second changing (or full repaint).
  if (repaint || _clkTm.seconds != lastSec) {
    lastSec = _clkTm.seconds;
    char wdl[12]; snprintf(wdl, sizeof(wdl), "%s %s %02d", DOW[clockDow()], MON[mi], _clkDt.date);
    char ssl[3]; snprintf(ssl, sizeof(ssl), "%02d", _clkTm.seconds);
    M5.Lcd.setTextDatum(MC_DATUM);
    M5.Lcd.setTextSize(3); M5.Lcd.setTextColor(p.text, p.bg);    M5.Lcd.drawString(hm, 170, 42);
    M5.Lcd.setTextSize(2); M5.Lcd.setTextColor(p.textDim, p.bg); M5.Lcd.drawString(ssl, 170, 72);
                                                                  M5.Lcd.drawString(wdl, 170, 102);
    M5.Lcd.setTextDatum(TL_DATUM);
    M5.Lcd.setTextSize(1);
  }

  // Pet on left at 5 fps. Clear includes the overlay-particle zone above
  // the body (y<30) — species draw Zzz/hearts there via BUDDY_Y_OVERLAY=6
  // which doesn't go through _yb, so the box has to cover it.
  static uint32_t lastPetTick = 0;
  if (millis() - lastPetTick >= 200) {
    lastPetTick = millis();
    if (buddyMode) {
      // ASCII glyphs don't self-clear; wipe the box each tick. Species
      // hardcode BUDDY_X_CENTER=67 / BUDDY_Y_OVERLAY=6 for particles so
      // keep portrait coords and just swap the surface — pet lands
      // upper-left of landscape, which is where we want it anyway.
      M5.Lcd.fillRect(0, 0, 115, 90, p.bg);
      buddyRenderTo(&M5.Lcd, activeState);
    } else {
      // Full-frame GIFs paint every pixel (transparent → pal.bg), so a
      // per-tick clear just adds a visible black flash between wipe and
      // last scanline. The entry fillScreen on paintedOrient change
      // already covers the surround.
      characterSetState(activeState);
      characterRenderTo(&M5.Lcd, 57, 45);
    }
  }
  M5.Lcd.setRotation(0);
}

PersonaState derive(const TamaState& s) {
  if (!s.connected)            return P_IDLE;
  if (s.sessionsWaiting > 0)   return P_ATTENTION;
  if (s.recentlyCompleted)     return P_CELEBRATE;
  if (s.sessionsRunning >= 3)  return P_BUSY;
  return P_IDLE;   // connected, 0+ sessions, nothing urgent — hang out
}

void triggerOneShot(PersonaState s, uint32_t durMs) {
  activeState = s;
  oneShotUntil = millis() + durMs;
}

bool checkShake() {
  float ax, ay, az;
  M5.Imu.getAccelData(&ax, &ay, &az);
  float mag = sqrtf(ax*ax + ay*ay + az*az);
  float delta = fabsf(mag - accelBaseline);
  accelBaseline = accelBaseline * 0.95f + mag * 0.05f;
  return delta > 0.8f;
}




// Persistent screen-level title row ("INFO  n/3") matching the PET header,
// then a per-page section label below it. The fixed title is the cue that
// B cycles pages here just like it does on PET.
static void _infoHeader(const Palette& p, int& y, const char* section, uint8_t page) {
  spr.setTextColor(p.text, p.bg);
  spr.setCursor(4, y); spr.print("Info");
  spr.setTextColor(p.textDim, p.bg);
  spr.setCursor(W - 28, y); spr.printf("%u/%u", page + 1, INFO_PAGES);
  y += 12;
  spr.setTextColor(p.body, p.bg);
  spr.setCursor(4, y); spr.print(section);
  y += 12;
}

void drawPasskey() {
  const Palette& p = characterPalette();
  spr.fillSprite(p.bg);
  spr.setTextSize(1);
  spr.setTextColor(p.textDim, p.bg);
  spr.setCursor(8, 56);  spr.print("BLUETOOTH PAIRING");
  spr.setCursor(8, 184); spr.print("enter on desktop:");
  spr.setTextSize(3);
  spr.setTextColor(p.text, p.bg);
  char b[8]; snprintf(b, sizeof(b), "%06lu", (unsigned long)blePasskey());
  spr.setCursor((W - 18 * 6) / 2, 110);
  spr.print(b);
}

void drawInfo() {
  const Palette& p = characterPalette();
  const int TOP = 70;
  spr.fillRect(0, TOP, W, H - TOP, p.bg);
  spr.setTextSize(1);
  int y = TOP + 2;
  auto ln = [&](const char* fmt, ...) {
    char b[32]; va_list a; va_start(a, fmt); vsnprintf(b, sizeof(b), fmt, a); va_end(a);
    spr.setCursor(4, y); spr.print(b); y += 8;
  };

  if (infoPage == 0) {
    _infoHeader(p, y, "ABOUT", infoPage);
    spr.setTextColor(p.textDim, p.bg);
    ln("I watch your Claude");
    ln("desktop sessions.");
    y += 6;
    ln("I sleep when nothing's");
    ln("happening, wake when");
    ln("you start working,");
    ln("get impatient when");
    ln("approvals pile up.");
    y += 6;
    spr.setTextColor(p.text, p.bg);
    ln("Press A on a prompt");
    ln("to approve from here.");
    y += 6;
    spr.setTextColor(p.textDim, p.bg);
    ln("18 species. Settings");
    ln("> ascii pet to cycle.");

  } else if (infoPage == 1) {
    _infoHeader(p, y, "BUTTONS", infoPage);
    spr.setTextColor(p.text, p.bg);    ln("A   front");
    spr.setTextColor(p.textDim, p.bg); ln("    next screen");
    ln("    approve prompt"); y += 4;
    spr.setTextColor(p.text, p.bg);    ln("B   right side");
    spr.setTextColor(p.textDim, p.bg); ln("    next page");
    ln("    deny prompt");
    ln("    hold = mic"); y += 4;
    spr.setTextColor(p.text, p.bg);    ln("hold A");
    spr.setTextColor(p.textDim, p.bg); ln("    menu"); y += 4;
    spr.setTextColor(p.text, p.bg);    ln("Power  left side");
    spr.setTextColor(p.textDim, p.bg); ln("    tap = screen off");
    ln("    hold 6s = off");

  } else if (infoPage == 2) {
    _infoHeader(p, y, "CLAUDE", infoPage);
    spr.setTextColor(p.textDim, p.bg);
    ln("  sessions  %u", tama.sessionsTotal);
    ln("  running   %u", tama.sessionsRunning);
    ln("  waiting   %u", tama.sessionsWaiting);
    y += 8;
    spr.setTextColor(p.text, p.bg);
    ln("LINK");
    spr.setTextColor(p.textDim, p.bg);
    ln("  via       %s", dataScenarioName());
    ln("  ble       %s", !bleConnected() ? "-" : bleSecure() ? "encrypted" : "OPEN");
    uint32_t age = (millis() - tama.lastUpdated) / 1000;
    ln("  last msg  %lus", (unsigned long)age);
    ln("  state     %s", stateNames[activeState]);

  } else if (infoPage == 3) {
    _infoHeader(p, y, "DEVICE", infoPage);

    int vBat_mV = M5.Power.getBatteryVoltage();
    int iBat_mA = M5.Power.getBatteryCurrent();
    int vBus_mV = M5.Power.getVBUSVoltage();
    int pct = (vBat_mV - 3200) / 10;   // (v-3.2)/(4.2-3.2)*100 = (v-3.2)*100 = (mv-3200)/10
    if (pct < 0) pct = 0; if (pct > 100) pct = 100;
    bool usb = vBus_mV > 4000;
    bool charging = usb && iBat_mA > 1;
    bool full = usb && vBat_mV > 4100 && iBat_mA < 10;

    spr.setTextColor(p.text, p.bg);
    spr.setTextSize(2);
    spr.setCursor(4, y);
    spr.printf("%d%%", pct);
    spr.setTextSize(1);
    spr.setTextColor(full ? GREEN : (charging ? HOT : p.textDim), p.bg);
    spr.setCursor(60, y + 4);
    spr.print(full ? "full" : (charging ? "charging" : (usb ? "usb" : "battery")));
    y += 20;

    spr.setTextColor(p.textDim, p.bg);
    ln("  battery  %d.%02dV", vBat_mV/1000, (vBat_mV%1000)/10);
    ln("  current  %+dmA", iBat_mA);
    if (usb) ln("  usb in   %d.%02dV", vBus_mV/1000, (vBus_mV%1000)/10);
    y += 8;

    spr.setTextColor(p.text, p.bg);
    ln("SYSTEM");
    spr.setTextColor(p.textDim, p.bg);
    if (ownerName()[0]) ln("  owner    %s", ownerName());
    uint32_t up = millis() / 1000;
    ln("  uptime   %luh %02lum", up / 3600, (up / 60) % 60);
    ln("  heap     %uKB", ESP.getFreeHeap() / 1024);
    ln("  bright   %u/4", brightLevel);
    ln("  sound    %s", settings().sound ? "on" : "off");
    ln("  bt       %s", settings().bt ? (dataBtActive() ? "linked" : "on") : "off");
    // StickS3 has no on-PMIC temperature sensor (AXP192-only feature).

  } else if (infoPage == 4) {
    _infoHeader(p, y, "BLUETOOTH", infoPage);
    bool linked = settings().bt && dataBtActive();

    spr.setTextColor(linked ? GREEN : (settings().bt ? HOT : p.textDim), p.bg);
    spr.setTextSize(2);
    spr.setCursor(4, y);
    spr.print(linked ? "linked" : (settings().bt ? "discover" : "off"));
    spr.setTextSize(1);
    y += 20;

    spr.setTextColor(p.textDim, p.bg);
    spr.setTextColor(p.text, p.bg);
    ln("  %s", btName);
    spr.setTextColor(p.textDim, p.bg);
    uint8_t mac[6] = {0};
    esp_read_mac(mac, ESP_MAC_BT);
    ln("  %02X:%02X:%02X:%02X:%02X:%02X",
       mac[0],mac[1],mac[2],mac[3],mac[4],mac[5]);
    y += 8;

    if (linked) {
      uint32_t age = (millis() - tama.lastUpdated) / 1000;
      ln("  last msg  %lus", (unsigned long)age);
    } else if (settings().bt) {
      spr.setTextColor(p.text, p.bg);
      ln("TO PAIR");
      spr.setTextColor(p.textDim, p.bg);
      ln(" Open Claude desktop");
      ln(" > Developer");
      ln(" > Hardware Buddy");
      y += 4;
      ln(" auto-connects via BLE");
    }

  } else {
    _infoHeader(p, y, "CREDITS", infoPage);
    spr.setTextColor(p.textDim, p.bg);
    ln("made by");
    y += 4;
    spr.setTextColor(p.text, p.bg);
    ln("Felix Rieseberg");
    y += 12;
    spr.setTextColor(p.textDim, p.bg);
    ln("source");
    y += 4;
    spr.setTextColor(p.text, p.bg);
    ln("github.com/anthropics");
    ln("/claude-desktop-buddy");
    y += 12;
    spr.setTextColor(p.textDim, p.bg);
    ln("hardware");
    y += 4;
#ifdef BUDDY_BOARD_S3
    ln("M5 StickS3");
    ln("ESP32-S3 + PY32");
#else
    ln("M5StickC Plus");
    ln("ESP32 + AXP192");
#endif
  }
}


static bool utf8HasVisibleText(const char* s) {
  if (!s) return false;
  while (*s) {
    if (*s == '\n') {
      s++;
      continue;
    }
    if (!utf8IsAsciiSpace(*s)) return true;
    s++;
  }
  return false;
}

enum UiScript : uint8_t { UI_ASCII, UI_CN, UI_JA, UI_KR };

static UiScript detectUiScript(const char* s) {
  bool sawHan = false;
  if (!s) return UI_ASCII;
  while (*s) {
    size_t n = 0;
    uint32_t cp = utf8Decode(s, &n);
    if ((cp >= 0x1100 && cp <= 0x11FF)
        || (cp >= 0x3130 && cp <= 0x318F)
        || (cp >= 0xAC00 && cp <= 0xD7AF)) {
      return UI_KR;
    }
    if ((cp >= 0x3040 && cp <= 0x30FF)
        || (cp >= 0x31F0 && cp <= 0x31FF)) {
      return UI_JA;
    }
    if ((cp >= 0x2E80 && cp <= 0x2FFF)
        || (cp >= 0x3000 && cp <= 0x303F)
        || (cp >= 0x3100 && cp <= 0x312F)
        || (cp >= 0x31A0 && cp <= 0x31BF)
        || (cp >= 0x3400 && cp <= 0x4DBF)
        || (cp >= 0x4E00 && cp <= 0x9FFF)
        || (cp >= 0xF900 && cp <= 0xFAFF)
        || (cp >= 0xFF01 && cp <= 0xFFEE)
        || (cp >= 0x20000 && cp <= 0x3FFFD)) {
      sawHan = true;
    }
    s += n ? n : 1;
  }
  return sawHan ? UI_CN : UI_ASCII;
}

static UiScript mergeUiScript(UiScript a, UiScript b) {
  return a != UI_ASCII ? a : b;
}

struct UiCompactLayout {
  uint8_t titleCols;
  uint8_t bodyCols;
  uint8_t narrowCols;
  uint8_t choiceCols;
  uint8_t multiCols;
  uint8_t bodyLH;
  uint8_t titleLH;
  uint8_t sectionGap;
  uint8_t footerPad;
};

static UiCompactLayout uiCompactLayoutFor(UiScript script) {
  if (script == UI_ASCII) return { 21, 21, 17, 16, 12, 8, 12, 4, 12 };
  return { 18, 18, 14, 12, 9, 11, 13, 5, 14 };
}

static const lgfx::IFont* uiBodyFontFor(UiScript script) {
  switch (script) {
    case UI_CN: return &fonts::efontCN_10;
    case UI_JA: return &fonts::efontJA_10;
    case UI_KR: return &fonts::efontKR_10;
    default: return &fonts::Font0;
  }
}

static const lgfx::IFont* uiTitleFontFor(UiScript script) {
  switch (script) {
    case UI_CN: return &fonts::efontCN_12;
    case UI_JA: return &fonts::efontJA_12;
    case UI_KR: return &fonts::efontKR_12;
    default: return &fonts::Font0;
  }
}

static uint8_t uiLineHeightFor(UiScript script) {
  return uiCompactLayoutFor(script).bodyLH;
}

static uint8_t uiPromptTitleColsFor(UiScript script) {
  return script == UI_ASCII ? 21 : 20;
}

static uint8_t uiPromptBodyColsFor(UiScript script) {
  return script == UI_ASCII ? 21 : 24;
}

static uint8_t uiPromptChoiceColsFor(UiScript script) {
  return script == UI_ASCII ? 16 : 18;
}

static uint8_t uiPromptMultiColsFor(UiScript script) {
  return script == UI_ASCII ? 12 : 14;
}

static void setUiBodyFont(const char* s) {
  spr.setFont(uiBodyFontFor(detectUiScript(s)));
  spr.setTextSize(1);
}

static void setUiTitleFont(const char* s) {
  spr.setFont(uiTitleFontFor(detectUiScript(s)));
  spr.setTextSize(1);
}

static bool utf8LineSlice(const char* src, uint8_t cols, char* out, size_t outSize, const char** next = nullptr) {
  const char* tail = src ? src : "";
  utf8SliceColumns(src, out, outSize, cols, &tail, true, true);
  if (next) *next = tail;
  return utf8HasVisibleText(tail);
}

// Greedy UTF-8-safe wrap into fixed-width rows. Continuation rows get a
// leading ASCII indent so the transcript still scans like the old layout.
static uint8_t wrapInto(const char* in, char* out, size_t rowSize, uint8_t maxRows, uint8_t width) {
  return utf8WrapInto(in, out, rowSize, maxRows, width, true);
}

static uint8_t wrapBlockInto(const char* in, char* out, size_t rowSize, uint8_t maxRows, uint8_t width) {
  return utf8WrapInto(in, out, rowSize, maxRows, width, false);
}

static bool eventVisible() {
  return tama.event.active
      && tama.event.ttlMs > 0
      && (millis() - tama.event.receivedMs) < tama.event.ttlMs
      && !tama.promptId[0]
      && tama.nPending == 0;
}

static void drawMicOverlay() {
  if (!micRecording) return;
  const Palette& p = characterPalette();
  int x = 4;
  int y = 54;
  int w = 78;
  int h = 13;
  spr.fillRoundRect(x, y, w, h, 3, PANEL);
  spr.drawRoundRect(x, y, w, h, 3, HOT);
  spr.fillCircle(x + 7, y + 6, 2, HOT);
  spr.setTextSize(1);
  spr.setFont(&fonts::Font0);
  spr.setTextColor(p.text, PANEL);
  uint32_t ds = (millis() - micStartedMs) / 100;
  spr.setCursor(x + 13, y + 3);
  spr.printf("REC %lu.%lus", (unsigned long)(ds / 10), (unsigned long)(ds % 10));
  int barW = 14;
  int fill = (int)((uint64_t)barW * (millis() - micStartedMs) / MIC_MAX_MS);
  if (fill > barW) fill = barW;
  spr.drawRect(x + w - barW - 4, y + 3, barW, 6, p.textDim);
  if (fill > 0) spr.fillRect(x + w - barW - 3, y + 4, fill, 4, HOT);
}

static void drawApproval() {
  const Palette& p = characterPalette();
  const int TOP = 70;
  UiScript toolScript = detectUiScript(tama.promptTool);
  UiScript hintScript = detectUiScript(tama.promptHint);
  UiScript layoutScript = mergeUiScript(toolScript, hintScript);
  UiCompactLayout layout = uiCompactLayoutFor(layoutScript);
  uint8_t titleCols = uiPromptTitleColsFor(toolScript);
  uint8_t bodyCols = uiPromptBodyColsFor(hintScript);
  uint8_t toolLen = utf8DisplayWidth(tama.promptTool);
  char toolLine[80];
  utf8LineSlice(tama.promptTool, titleCols, toolLine, sizeof(toolLine));
  char hintRows[4][96] = {};
  uint8_t hintCount = wrapBlockInto(tama.promptHint, &hintRows[0][0], sizeof(hintRows[0]), 4, bodyCols);
  if (hintCount == 0) hintCount = 1;
  int titleH = (toolScript == UI_ASCII && toolLen <= 10) ? 16 : uiCompactLayoutFor(toolScript).titleLH;
  spr.fillRect(0, TOP, W, H - TOP, p.bg);
  spr.drawFastHLine(0, TOP, W, p.textDim);

  spr.setTextSize(1);
  spr.setTextColor(p.textDim, p.bg);
  spr.setCursor(4, TOP + 4);
  uint32_t waited = (millis() - promptArrivedMs) / 1000;
  if (waited >= 10) spr.setTextColor(HOT, p.bg);
  spr.printf("approve? %lus", (unsigned long)waited);

  // Size 2 only if it fits one line (~10 chars at 12px on 135px screen)
  spr.setTextColor(p.text, p.bg);
  if (toolScript == UI_ASCII) {
    spr.setFont(&fonts::Font0);
    spr.setTextSize(toolLen <= 10 ? 2 : 1);
  } else {
    spr.setFont(uiTitleFontFor(toolScript));
    spr.setTextSize(1);
  }
  int titleY = TOP + 18;
  spr.setCursor(4, titleY);
  spr.print(toolLine);
  spr.setFont(&fonts::Font0);
  spr.setTextSize(1);

  spr.setTextColor(p.textDim, p.bg);
  int hintY = titleY + titleH + layout.sectionGap;
  for (uint8_t i = 0; i < hintCount && i < 4; i++) {
    setUiBodyFont(hintRows[i]);
    spr.setCursor(4, hintY + i * uiLineHeightFor(hintScript));
    spr.print(hintRows[i]);
  }
  spr.setFont(&fonts::Font0);

  int footerY = H - layout.footerPad;
  if (responseSent) {
    spr.setTextColor(p.textDim, p.bg);
    spr.setCursor(4, footerY);
    spr.print("sent...");
  } else {
    spr.setTextColor(GREEN, p.bg);
    spr.setCursor(4, footerY);
    spr.print("A: approve");
    spr.setTextColor(HOT, p.bg);
    spr.setCursor(W - 48, footerY);
    spr.print("B: deny");
  }
}

static void fmtDur(uint32_t s, char* out, size_t n) {
  if (s < 60) snprintf(out, n, "%lus", (unsigned long)s);
  else if (s < 3600) snprintf(out, n, "%lum", (unsigned long)(s / 60));
  else snprintf(out, n, "%luh%02lum", (unsigned long)(s / 3600), (unsigned long)((s / 60) % 60));
}

static void drawAction() {
  if (tama.nPending == 0) { drawApproval(); return; }
  const Palette& p = characterPalette();
  const int TOP = 70;
  PendingDecision& d = tama.pending[0];
  UiScript titleScript = detectUiScript(d.title[0] ? d.title : "Decision");
  UiScript bodyScript = detectUiScript(d.body);
  UiScript optionScript = UI_ASCII;
  for (uint8_t i = 0; i < d.nOptions; i++) {
    optionScript = mergeUiScript(optionScript, detectUiScript(d.options[i].label));
  }
  UiScript layoutScript = mergeUiScript(mergeUiScript(titleScript, bodyScript), optionScript);
  UiCompactLayout layout = uiCompactLayoutFor(layoutScript);
  uint8_t titleCols = uiPromptTitleColsFor(titleScript);
  uint8_t bodyCols = uiPromptBodyColsFor(bodyScript);
  uint8_t choiceCols = uiPromptChoiceColsFor(optionScript);
  uint8_t multiCols = uiPromptMultiColsFor(optionScript);
  const char* titleText = d.title[0] ? d.title : "Decision";
  uint8_t titleWidth = utf8DisplayWidth(titleText);
  char titleLine[96];
  utf8LineSlice(titleText, titleCols, titleLine, sizeof(titleLine));
  uint8_t bodyMaxRows = 2;
  if ((strcmp(d.kind, "single_choice") == 0
       || (strcmp(d.kind, "free_text_required") == 0 && d.nOptions > 0))) {
    bodyMaxRows = 3;
  } else if (strcmp(d.kind, "notice") == 0 || strcmp(d.kind, "free_text_required") == 0) {
    bodyMaxRows = 4;
  }
  char bodyRows[4][96] = {};
  uint8_t bodyCount = wrapBlockInto(d.body, &bodyRows[0][0], sizeof(bodyRows[0]), bodyMaxRows, bodyCols);
  if (bodyCount == 0) bodyCount = 1;
  int titleH = (titleScript == UI_ASCII && titleWidth <= 10) ? 16 : uiCompactLayoutFor(titleScript).titleLH;
  int footerY = H - layout.footerPad;
  int optionTop = footerY - layout.bodyLH - layout.sectionGap;
  if ((strcmp(d.kind, "single_choice") == 0
       || (strcmp(d.kind, "free_text_required") == 0 && d.nOptions > 0))
      && d.nOptions > 0) {
    optionTop = footerY - layout.bodyLH - layout.sectionGap;
  } else if (strcmp(d.kind, "multi_choice") == 0 && d.nOptions > 0) {
    optionTop = footerY - layout.sectionGap - d.nOptions * layout.bodyLH;
  } else if (strcmp(d.kind, "notice") == 0 || strcmp(d.kind, "free_text_required") == 0) {
    optionTop = footerY - layout.bodyLH - layout.sectionGap;
  }
  spr.fillRect(0, TOP, W, H - TOP, p.bg);
  spr.drawFastHLine(0, TOP, W, p.textDim);
  spr.setTextSize(1);

  char age[12];
  fmtDur(d.pendingS ? d.pendingS : ((millis() - promptArrivedMs) / 1000), age, sizeof(age));
  spr.setTextColor(HOT, p.bg);
  spr.setCursor(4, TOP + 4);
  spr.printf("%s  wait %s", d.kind[0] ? d.kind : "action", age);

  spr.setTextColor(p.text, p.bg);
  if (titleScript == UI_ASCII) {
    spr.setFont(&fonts::Font0);
    spr.setTextSize(titleWidth <= 10 ? 2 : 1);
  } else {
    spr.setFont(uiTitleFontFor(titleScript));
    spr.setTextSize(1);
  }
  int titleY = TOP + 18;
  spr.setCursor(4, titleY);
  spr.print(titleLine);
  spr.setFont(&fonts::Font0);
  spr.setTextSize(1);

  spr.setTextColor(p.textDim, p.bg);
  int bodyY = titleY + titleH + layout.sectionGap;
  for (uint8_t i = 0; i < bodyCount && i < bodyMaxRows; i++) {
    setUiBodyFont(bodyRows[i]);
    spr.setCursor(4, bodyY + i * uiLineHeightFor(bodyScript));
    spr.print(bodyRows[i]);
  }
  spr.setFont(&fonts::Font0);

  if ((strcmp(d.kind, "single_choice") == 0
       || (strcmp(d.kind, "free_text_required") == 0 && d.nOptions > 0))
      && d.nOptions > 0) {
    DecisionOption& opt = d.options[d.selected];
    char optLine[64];
    utf8LineSlice(opt.label, choiceCols, optLine, sizeof(optLine));
    spr.setTextColor(p.body, p.bg);
    spr.setCursor(4, optionTop);
    spr.printf("%u/%u ", d.selected + 1, d.nOptions);
    setUiBodyFont(optLine);
    spr.print(optLine);
    spr.setFont(&fonts::Font0);
    spr.setTextColor(GREEN, p.bg);
    spr.setCursor(4, footerY); spr.print("A: send");
    spr.setTextColor(p.textDim, p.bg);
    spr.setCursor(W - 42, footerY); spr.print("B: next");
  } else if (strcmp(d.kind, "multi_choice") == 0 && d.nOptions > 0) {
    int y = optionTop;
    for (uint8_t i = 0; i < d.nOptions && i < MAX_OPTIONS; i++) {
      DecisionOption& opt = d.options[i];
      char optLine[64];
      utf8LineSlice(opt.label, multiCols, optLine, sizeof(optLine));
      spr.setTextColor(i == d.selected ? p.body : p.textDim, p.bg);
      spr.setCursor(4, y);
      spr.printf("%c [%c] ", i == d.selected ? '>' : ' ', opt.selected ? 'x' : ' ');
      setUiBodyFont(optLine);
      spr.print(optLine);
      spr.setFont(&fonts::Font0);
      y += layout.bodyLH;
    }
    spr.setTextColor(GREEN, p.bg);
    spr.setCursor(4, footerY); spr.print("A: toggle");
    spr.setTextColor(p.textDim, p.bg);
    spr.setCursor(W - 42, footerY); spr.print("B: next");
  } else if (strcmp(d.kind, "notice") == 0 || strcmp(d.kind, "free_text_required") == 0) {
    spr.setTextColor(p.body, p.bg);
    spr.setCursor(4, optionTop);
    spr.print("type on host");
    spr.setTextColor(GREEN, p.bg);
    spr.setCursor(4, footerY); spr.print("A: focus");
    spr.setTextColor(p.textDim, p.bg);
    spr.setCursor(W - 42, footerY); spr.print("B: wait");
  } else if (responseSent) {
    spr.setTextColor(p.textDim, p.bg);
    spr.setCursor(4, footerY); spr.print("sent...");
  } else {
    spr.setTextColor(GREEN, p.bg);
    spr.setCursor(4, footerY); spr.print("A: approve");
    spr.setTextColor(HOT, p.bg);
    spr.setCursor(W - 48, footerY); spr.print("B: deny");
  }
}

static void tinyHeart(int x, int y, bool filled, uint16_t col) {
  if (filled) {
    spr.fillCircle(x - 2, y, 2, col);
    spr.fillCircle(x + 2, y, 2, col);
    spr.fillTriangle(x - 4, y + 1, x + 4, y + 1, x, y + 5, col);
  } else {
    spr.drawCircle(x - 2, y, 2, col);
    spr.drawCircle(x + 2, y, 2, col);
    spr.drawLine(x - 4, y + 1, x, y + 5, col);
    spr.drawLine(x + 4, y + 1, x, y + 5, col);
  }
}

static void drawPetStats(const Palette& p) {
  const int TOP = 70;
  spr.fillRect(0, TOP, W, H - TOP, p.bg);
  spr.setTextSize(1);
  int y = TOP + 16;

  spr.setTextColor(p.textDim, p.bg);
  spr.setCursor(6, y - 2); spr.print("mood");
  uint8_t mood = statsMoodTier();
  uint16_t moodCol = (mood >= 3) ? RED : (mood >= 2) ? HOT : p.textDim;
  for (int i = 0; i < 4; i++) tinyHeart(54 + i * 16, y + 2, i < mood, moodCol);

  y += 20;
  spr.setCursor(6, y - 2); spr.print("fed");
  uint8_t fed = statsFedProgress();
  for (int i = 0; i < 10; i++) {
    int px = 38 + i * 9;
    if (i < fed) spr.fillCircle(px, y + 1, 2, p.body);
    else spr.drawCircle(px, y + 1, 2, p.textDim);
  }

  y += 20;
  spr.setCursor(6, y - 2); spr.print("energy");
  uint8_t en = statsEnergyTier();
  uint16_t enCol = (en >= 4) ? 0x07FF : (en >= 2) ? 0xFFE0 : HOT;
  for (int i = 0; i < 5; i++) {
    int px = 54 + i * 13;
    if (i < en) spr.fillRect(px, y - 2, 9, 6, enCol);
    else spr.drawRect(px, y - 2, 9, 6, p.textDim);
  }

  y += 24;
  spr.fillRoundRect(6, y - 2, 42, 14, 3, p.body);
  spr.setTextColor(p.bg, p.body);
  spr.setCursor(11, y + 1); spr.printf("Lv %u", stats().level);

  y += 20;
  spr.setTextColor(p.textDim, p.bg);
  spr.setCursor(6, y);
  spr.printf("approved %u", stats().approvals);
  spr.setCursor(6, y + 10);
  spr.printf("denied   %u", stats().denials);
  uint32_t nap = stats().napSeconds;
  spr.setCursor(6, y + 20);
  spr.printf("napped   %luh%02lum", nap/3600, (nap/60)%60);
  auto tokFmt = [&](const char* label, uint32_t v, int yPx) {
    spr.setCursor(6, yPx);
    if (v >= 1000000)   spr.printf("%s%lu.%luM", label, v/1000000, (v/100000)%10);
    else if (v >= 1000) spr.printf("%s%lu.%luK", label, v/1000, (v/100)%10);
    else                spr.printf("%s%lu", label, v);
  };
  tokFmt("tokens   ", stats().tokens, y + 30);
  tokFmt("today    ", tama.tokensToday, y + 40);
}

static void drawPetHowTo(const Palette& p) {
  const int TOP = 70;
  spr.fillRect(0, TOP, W, H - TOP, p.bg);
  spr.setTextSize(1);
  int y = TOP + 2;
  auto ln = [&](uint16_t c, const char* s) {
    spr.setTextColor(c, p.bg); spr.setCursor(6, y); spr.print(s); y += 9;
  };
  auto gap = [&]() { y += 4; };

  y += 12;  // room for the PET header drawn by drawPet()

  ln(p.body,    "MOOD");
  ln(p.textDim, " approve fast = up");
  ln(p.textDim, " deny lots = down"); gap();

  ln(p.body,    "FED");
  ln(p.textDim, " 50K tokens =");
  ln(p.textDim, " level up + confetti"); gap();

  ln(p.body,    "ENERGY");
  ln(p.textDim, " face-down to nap");
  ln(p.textDim, " refills to full"); gap();

  ln(p.textDim, "idle 30s = off");
  ln(p.textDim, "any button = wake"); gap();

  ln(p.textDim, "A: screens  B: page");
  ln(p.textDim, "hold A: menu");
}

void drawPet() {
  const Palette& p = characterPalette();
  int y = 70;

  if (petPage == 0) drawPetStats(p);
  else drawPetHowTo(p);

  // Header on top of whichever page drew — title left, counter right
  spr.setTextSize(1);
  spr.setTextColor(p.text, p.bg);
  spr.setCursor(4, y + 2);
  if (ownerName()[0]) {
    spr.printf("%s's %s", ownerName(), petName());
  } else {
    spr.print(petName());
  }
  spr.setTextColor(p.textDim, p.bg);
  spr.setCursor(W - 28, y + 2);
  spr.printf("%u/%u", petPage + 1, PET_PAGES);
}

void drawHUD() {
  if (tama.promptId[0] || tama.nPending > 0) { drawAction(); return; }
  const Palette& p = characterPalette();
  int LH = 8;
  spr.setTextSize(1);

  if (tama.lineGen != lastLineGen) { msgScroll = 0; lastLineGen = tama.lineGen; wake(); }

  if (tama.nLines == 0) {
    UiScript msgScript = detectUiScript(tama.msg);
    UiCompactLayout layout = uiCompactLayoutFor(msgScript);
    char msgLine[80];
    utf8LineSlice(tama.msg, layout.bodyCols, msgLine, sizeof(msgLine));
    LH = uiLineHeightFor(msgScript);
    const int SHOW = 3;
    const int hudArea = SHOW * LH + 4;
    spr.fillRect(0, H - hudArea, W, hudArea, p.bg);
    spr.setTextColor(p.text, p.bg);
    setUiBodyFont(msgLine);
    spr.setCursor(4, H - LH - 2);
    spr.print(msgLine);
    spr.setFont(&fonts::Font0);
    if (!settings().sound) {
      spr.setTextColor(HOT, p.bg);
      spr.setCursor(W - 28, H - hudArea + 2);
      spr.print("mute");
    }
    return;
  }

  // Wrap all transcript lines into a flat display buffer. Track which
  // transcript index each display row came from, so we can dim older ones.
  static char disp[32][80];
  static uint8_t srcOf[32];
  uint8_t nDisp = 0;
  UiScript hudScript = UI_ASCII;
  for (uint8_t i = 0; i < tama.nLines && nDisp < 32; i++) {
    UiScript rowScript = detectUiScript(tama.lines[i]);
    uint8_t got = wrapInto(
        tama.lines[i],
        &disp[nDisp][0],
        sizeof(disp[0]),
        32 - nDisp,
        uiCompactLayoutFor(rowScript).bodyCols);
    for (uint8_t j = 0; j < got; j++) srcOf[nDisp + j] = i;
    hudScript = mergeUiScript(hudScript, rowScript);
    nDisp += got;
  }
  UiCompactLayout layout = uiCompactLayoutFor(hudScript);
  const int SHOW = 3;
  LH = uiLineHeightFor(hudScript);
  const int hudArea = SHOW * LH + 4;
  spr.fillRect(0, H - hudArea, W, hudArea, p.bg);

  uint8_t maxBack = (nDisp > SHOW) ? (nDisp - SHOW) : 0;
  if (msgScroll > maxBack) msgScroll = maxBack;

  int end = (int)nDisp - msgScroll;
  int start = end - SHOW; if (start < 0) start = 0;
  uint8_t newest = tama.nLines - 1;
  for (int i = 0; start + i < end; i++) {
    uint8_t row = start + i;
    bool fresh = (srcOf[row] == newest) && (msgScroll == 0);
    spr.setTextColor(fresh ? p.text : p.textDim, p.bg);
    setUiBodyFont(disp[row]);
    spr.setCursor(4, H - hudArea + 2 + i * LH);
    spr.print(disp[row]);
    spr.setFont(&fonts::Font0);
  }
  if (msgScroll > 0) {
    spr.setTextColor(p.body, p.bg);
    spr.setCursor(W - 18, H - LH - 2);
    spr.printf("-%u", msgScroll);
  }
  if (!settings().sound) {
    spr.setTextColor(HOT, p.bg);
    spr.setCursor(W - 28, H - hudArea + 2);
    spr.print("mute");
  }
}

static void drawFocusedSession() {
  const Palette& p = characterPalette();
  const int TOP = 70;
  spr.fillRect(0, TOP, W, H - TOP, p.bg);
  spr.setTextSize(1);

  SessionSummary* s = nullptr;
  for (uint8_t i = 0; i < tama.nSessions; i++) {
    if (tama.sessions[i].focused) { s = &tama.sessions[i]; break; }
  }
  if (!s && tama.nSessions > 0) s = &tama.sessions[0];

  int y = TOP + 2;
  spr.setTextColor(p.text, p.bg);
  spr.setCursor(4, y); spr.print("Session"); y += 12;

  if (!s) {
    spr.setTextColor(p.textDim, p.bg);
    spr.setCursor(4, y); spr.print(tama.connected ? "No sessions" : "No bridge");
    return;
  }

  const char* project = s->project[0] ? s->project : tama.project;
  const char* branch = s->branch[0] ? s->branch : tama.branch;
  const char* model = s->model[0] ? s->model : tama.model;
  const char* last = s->last[0] ? s->last : tama.assistantMsg;
  UiScript layoutScript = UI_ASCII;
  layoutScript = mergeUiScript(layoutScript, detectUiScript(project));
  layoutScript = mergeUiScript(layoutScript, detectUiScript(branch));
  layoutScript = mergeUiScript(layoutScript, detectUiScript(model));
  layoutScript = mergeUiScript(layoutScript, detectUiScript(last));
  UiCompactLayout layout = uiCompactLayoutFor(layoutScript);
  UiCompactLayout modelLayout = uiCompactLayoutFor(detectUiScript(model));

  char dur[12];
  char projectLine[96], branchLine[96], modelLine[64], last0[96], last1[96];
  const char* lastNext = nullptr;
  utf8LineSlice(project, layout.bodyCols, projectLine, sizeof(projectLine));
  utf8LineSlice(branch, layout.bodyCols, branchLine, sizeof(branchLine));
  utf8LineSlice(model, modelLayout.choiceCols, modelLine, sizeof(modelLine));
  bool lastMore = utf8LineSlice(last, layout.bodyCols, last0, sizeof(last0), &lastNext);
  fmtDur(s->pendingS ? s->pendingS : s->elapsedS, dur, sizeof(dur));
  spr.setTextColor(p.body, p.bg);
  setUiBodyFont(projectLine);
  spr.setCursor(4, y); spr.print(projectLine); y += layout.bodyLH;
  spr.setTextColor(p.textDim, p.bg);
  setUiBodyFont(branchLine);
  spr.setCursor(4, y); spr.print(branchLine); y += layout.bodyLH;
  spr.setFont(&fonts::Font0);
  spr.setCursor(4, y); spr.printf("%s %s  dirty %d", s->phase, dur, s->dirty); y += layout.bodyLH;
  spr.setCursor(4, y); spr.print("model ");
  setUiBodyFont(modelLine);
  spr.print(modelLine); y += layout.bodyLH + layout.sectionGap;
  spr.setTextColor(p.text, p.bg);
  setUiBodyFont(last0);
  spr.setCursor(4, y); spr.print(last0); y += layout.bodyLH;
  if (lastMore) {
    utf8LineSlice(lastNext, layout.bodyCols, last1, sizeof(last1));
    setUiBodyFont(last1);
    spr.setCursor(4, y); spr.print(last1);
  }
  spr.setFont(&fonts::Font0);
}

static void drawSessionList() {
  const Palette& p = characterPalette();
  const int TOP = 70;
  spr.fillRect(0, TOP, W, H - TOP, p.bg);
  spr.setTextSize(1);
  if (sessionPage >= tama.nSessions && tama.nSessions > 0) sessionPage = 0;

  int y = TOP + 2;
  spr.setTextColor(p.text, p.bg);
  spr.setCursor(4, y); spr.print("Sessions");
  spr.setTextColor(p.textDim, p.bg);
  spr.setCursor(W - 28, y); spr.printf("%u/%u", tama.nSessions ? sessionPage + 1 : 0, tama.nSessions);
  y += 16;

  if (tama.nSessions == 0) {
    spr.setTextColor(p.textDim, p.bg);
    spr.setCursor(4, y); spr.print("No sessions");
    return;
  }
  SessionSummary& s = tama.sessions[sessionPage];
  UiScript layoutScript = UI_ASCII;
  layoutScript = mergeUiScript(layoutScript, detectUiScript(s.project));
  layoutScript = mergeUiScript(layoutScript, detectUiScript(s.branch));
  layoutScript = mergeUiScript(layoutScript, detectUiScript(s.last));
  UiCompactLayout layout = uiCompactLayoutFor(layoutScript);
  char dur[12];
  char projectLine[96], branchLine[96], lastLine[96];
  utf8LineSlice(s.project, layout.bodyCols, projectLine, sizeof(projectLine));
  utf8LineSlice(s.branch, layout.bodyCols, branchLine, sizeof(branchLine));
  utf8LineSlice(s.last, layout.bodyCols, lastLine, sizeof(lastLine));
  fmtDur(s.pendingS ? s.pendingS : s.elapsedS, dur, sizeof(dur));
  spr.setTextColor(s.focused ? GREEN : p.body, p.bg);
  setUiBodyFont(projectLine);
  spr.setCursor(4, y); spr.print(projectLine); y += layout.bodyLH;
  spr.setTextColor(p.textDim, p.bg);
  setUiBodyFont(branchLine);
  spr.setCursor(4, y); spr.print(branchLine); y += layout.bodyLH;
  spr.setFont(&fonts::Font0);
  spr.setCursor(4, y); spr.printf("%s %s", s.phase, dur); y += layout.bodyLH + layout.sectionGap;
  spr.setTextColor(p.text, p.bg);
  setUiBodyFont(lastLine);
  spr.setCursor(4, y); spr.print(lastLine);
  spr.setFont(&fonts::Font0);
  spr.setTextColor(GREEN, p.bg);
  spr.setCursor(4, H - layout.footerPad); spr.print("A: focus");
  spr.setTextColor(p.textDim, p.bg);
  spr.setCursor(W - 42, H - layout.footerPad); spr.print("B: next");
}

static void drawEventOverlay() {
  const Palette& p = characterPalette();
  uint32_t age = millis() - tama.event.receivedMs;
  uint32_t left = (age < tama.event.ttlMs) ? (tama.event.ttlMs - age) : 0;
  UiScript titleScript = detectUiScript(tama.event.title[0] ? tama.event.title : tama.event.kind);
  UiScript bodyScript = detectUiScript(tama.event.text);
  UiScript layoutScript = mergeUiScript(titleScript, bodyScript);
  UiCompactLayout layout = uiCompactLayoutFor(layoutScript);
  int mw = layoutScript == UI_ASCII ? 118 : 124;
  spr.setTextSize(1);
  char titleLine[80], text0[80], text1[80];
  const char* textNext = nullptr;
  utf8LineSlice(tama.event.title[0] ? tama.event.title : tama.event.kind, uiCompactLayoutFor(titleScript).narrowCols, titleLine, sizeof(titleLine));
  bool moreText = utf8LineSlice(tama.event.text, uiCompactLayoutFor(bodyScript).narrowCols, text0, sizeof(text0), &textNext);
  int mh = 26 + uiCompactLayoutFor(titleScript).titleLH + (moreText ? 2 : 1) * uiLineHeightFor(bodyScript);
  if (mh < 72) mh = 72;
  int mx = (W - mw) / 2, my = H - mh - 10;
  spr.fillRoundRect(mx, my, mw, mh, 4, PANEL);
  spr.drawRoundRect(mx, my, mw, mh, 4, strcmp(tama.event.kind, "error") == 0 ? HOT : GREEN);
  spr.setTextColor(p.text, PANEL);
  setUiTitleFont(titleLine);
  spr.setCursor(mx + 6, my + 8);
  spr.print(titleLine);
  spr.setTextColor(p.textDim, PANEL);
  setUiBodyFont(text0);
  int textY = my + 8 + uiCompactLayoutFor(titleScript).titleLH + layout.sectionGap;
  spr.setCursor(mx + 6, textY);
  spr.print(text0);
  if (moreText) {
    utf8LineSlice(textNext, uiCompactLayoutFor(bodyScript).narrowCols, text1, sizeof(text1));
    setUiBodyFont(text1);
    spr.setCursor(mx + 6, textY + uiLineHeightFor(bodyScript));
    spr.print(text1);
  }
  spr.setFont(&fonts::Font0);
  int barW = mw - 12;
  spr.drawRect(mx + 6, my + mh - 14, barW, 5, p.textDim);
  int fill = tama.event.ttlMs ? (int)((uint64_t)barW * left / tama.event.ttlMs) : 0;
  if (fill > 1) spr.fillRect(mx + 7, my + mh - 13, fill - 2, 3, p.body);
}

void setup() {
  // M5Unified's begin() initializes Display, Imu, Rtc, Speaker, and the
  // power management on the detected board (StickS3 → PY32 PMIC), so the
  // old Imu.Init/Beep.begin/pinMode(LED) calls are no longer needed.
  auto cfg = M5.config();
  M5.begin(cfg);
#ifdef BUDDY_BOARD_S3
  Serial.setRxBufferSize(1024);
  Serial.begin(115200);
  // Native-USB S3: when no host is reading CDC, Serial writes can block
  // for a long time (default per-byte timeout accumulates). Zero means
  // fire-and-forget — writes drop silently instead of stalling boot.
  // StickS3 uses HWCDC here, so only the TX timeout control is available.
  Serial.setTxTimeoutMs(0);
#endif
  M5.Speaker.begin();
  M5.Speaker.setVolume(255);
  M5.Speaker.setAllChannelVolume(255);
  M5.Lcd.setRotation(0);
  startBt();
#ifndef BUDDY_BOARD_S3
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, HIGH);   // active-low: HIGH = off
#endif
  applyBrightness();
  lastInteractMs = millis();
  statsLoad();
  settingsLoad();
  petNameLoad();
  buddyInit();

  // BLE stays always-on; s.bt is stored as a preference only.
  spr.createSprite(W, H);
  characterInit(nullptr);  // scan /characters/ for whatever is installed
  gifAvailable = characterLoaded();
  // species NVS: 0..N-1 = ASCII species, 0xFF = use GIF (also the default,
  // so a fresh install lands on the GIF). With no GIF installed, 0xFF falls
  // through to buddyInit()'s clamped default.
  buddyMode = !(gifAvailable && speciesIdxLoad() == SPECIES_GIF);
  applyDisplayMode();

  {
    const Palette& p = characterPalette();
    spr.fillSprite(p.bg);
    spr.setTextDatum(MC_DATUM);
    spr.setTextSize(2);
    if (ownerName()[0]) {
      char line[40];
      snprintf(line, sizeof(line), "%s's", ownerName());
      spr.setTextColor(p.text, p.bg);   spr.drawString(line, W/2, H/2 - 12);
      spr.setTextColor(p.body, p.bg);   spr.drawString(petName(), W/2, H/2 + 12);
    } else {
      // First boot, no owner pushed yet — say hi.
      spr.setTextColor(p.body, p.bg);   spr.drawString("Hello!", W/2, H/2 - 12);
      spr.setTextSize(1);
      spr.setTextColor(p.textDim, p.bg);
      spr.drawString("a buddy appears", W/2, H/2 + 12);
    }
    spr.setTextDatum(TL_DATUM);
    spr.setTextSize(1);
    spr.pushSprite(0, 0);
    delay(1800);
  }

  Serial.printf("buddy: %s\n", buddyMode ? "ASCII mode" : "GIF character loaded");
}

void loop() {
  M5.update();
  t++;
  uint32_t now = millis();

  dataPoll(&tama);
  if (statsPollLevelUp()) triggerOneShot(P_CELEBRATE, 3000);
  baseState = derive(tama);

  // After waking the screen, hold sleep for 12s so users see the wake-up
  // animation. Urgent states (attention, celebrate, busy) override this.
  if (baseState == P_IDLE && (int32_t)(now - wakeTransitionUntil) < 0) baseState = P_SLEEP;

  if ((int32_t)(now - oneShotUntil) >= 0) activeState = baseState;

  // Attention indicator: blink at 2Hz, gated by the `led` preference.
  // On the original StickC Plus this drives the physical red LED; on
  // StickS3 (no LED) it drives a red border drawn into the sprite just
  // before pushSprite.
#ifdef BUDDY_BOARD_S3
  alertBorderActive = (activeState == P_ATTENTION) && settings().led
                      && ((now / 250) & 1);
#else
  if (activeState == P_ATTENTION && settings().led) {
    digitalWrite(LED_PIN, (now / 400) % 2 ? LOW : HIGH);
  } else {
    digitalWrite(LED_PIN, HIGH);   // off
  }
#endif

  // shake → dizzy + force scenario advance
  if (now - lastShakeCheck > 50) {
    lastShakeCheck = now;
    if (!menuOpen && !screenOff && checkShake() && (int32_t)(now - oneShotUntil) >= 0) {
      wake();
      triggerOneShot(P_DIZZY, 2000);
      Serial.println("shake: dizzy");
    }
  }

  bool promptChanged = strcmp(tama.promptId, lastPromptId) != 0;
  bool pendingChanged = tama.pendingGen != lastPendingGen;
  bool samePromptAndPendingArrival = promptChanged
                                  && pendingChanged
                                  && tama.promptId[0]
                                  && tama.nPending > 0
                                  && strcmp(tama.promptId, tama.pending[0].id) == 0;
  bool inputRequiredCue = false;

  // BtnA: step through fake scenarios
  // Prompt arrival: wake, reset response flag, and surface the approval screen.
  if (promptChanged) {
    utf8SafeCopy(lastPromptId, sizeof(lastPromptId), tama.promptId);
    responseSent = false;
    if (tama.promptId[0]) {
      promptArrivedMs = millis();
      wake();
      if (!samePromptAndPendingArrival) inputRequiredCue = true;
      // Jump to the approval screen no matter what was open — drawApproval
      // only runs from drawHUD which only runs in DISP_NORMAL.
      displayMode = DISP_NORMAL;
      menuOpen = settingsOpen = resetOpen = false;
      applyDisplayMode();
      characterInvalidate();
      if (buddyMode) buddyInvalidate();
    }
  }
  if (pendingChanged) {
    lastPendingGen = tama.pendingGen;
    if (tama.nPending > 0) {
      wake();
      inputRequiredCue = true;
    }
  }
  if (inputRequiredCue) toneInputRequired();
  if (tama.eventGen != lastEventGen) {
    lastEventGen = tama.eventGen;
    if (tama.event.active) {
      if (strcmp(tama.event.kind, "error") == 0) toneEventError();
      else if (strcmp(tama.event.kind, "complete") == 0) {
        toneComplete();
      } else {
        toneEventNeutral();
      }
    }
  }

  bool inPrompt = tama.promptId[0] && !responseSent;
  bool awaitingPromptClear = responseSent && (tama.promptId[0] || tama.nPending > 0);

  // Safety net: we answered a prompt but the host never cleared it (it timed
  // out or the BLE link dropped). Without this the approval screen sticks
  // forever with the buttons intentionally ignored. After a grace period,
  // dismiss locally and return to normal so the device is always recoverable.
  if (awaitingPromptClear && responseSentMs &&
      (millis() - responseSentMs > PROMPT_CLEAR_TIMEOUT_MS)) {
    tama.promptId[0] = '\0';
    tama.nPending = 0;
    lastPromptId[0] = '\0';
    lastPendingGen = tama.pendingGen;
    responseSent = false;
    responseSentMs = 0;
    awaitingPromptClear = false;
    inPrompt = false;
    displayMode = DISP_NORMAL;
    menuOpen = settingsOpen = resetOpen = false;
    applyDisplayMode();
    characterInvalidate();
    if (buddyMode) buddyInvalidate();
    Serial.println("prompt: local clear timeout (host never cleared)");
  }

  if (micRecording) inPrompt = false;
  syncCompanionPeek();

  // Button-press wake. Track which button woke the screen so its full
  // press cycle (including long-press) is swallowed — you don't want
  // BtnA-to-wake to also cycle displayMode or open the menu.
  if (M5.BtnA.isPressed() || M5.BtnB.isPressed()) {
    if (screenOff) {
      if (M5.BtnA.isPressed()) swallowBtnA = true;
      if (M5.BtnB.isPressed()) swallowBtnB = true;
    }
    wake();
  }

  // Power button (left side): short-press toggles screen off.
  // M5Unified exposes it as BtnPWR; long-press hardware-off is still
  // handled by the PMIC firmware.
  if (M5.BtnPWR.wasClicked()) {
    if (screenOff) {
      wake();
    } else {
      M5.Display.sleep();
      screenOff = true;
    }
  }

  if (M5.BtnA.pressedFor(600) && !btnALong && !swallowBtnA) {
    btnALong = true;
    if (awaitingPromptClear) {
      // Ignore duplicate presses while the host clears the sent prompt.
    } else if (inPrompt && tama.nPending > 0 && strcmp(tama.pending[0].kind, "multi_choice") == 0 && tama.pending[0].nOptions > 0) {
      PendingDecision& d = tama.pending[0];
      if (multiChoiceCount(d) > 0) {
        sendAnswerChoices(d);
        responseSent = true;
        responseSentMs = millis();
        toneAnswerSent();
      } else {
        toneDenied();
      }
    } else {
      toneUiClick();
      if (resetOpen) { resetOpen = false; }
      else if (settingsOpen) { settingsOpen = false; characterInvalidate(); }
      else {
        menuOpen = !menuOpen;
        menuSel = 0;
        if (!menuOpen) characterInvalidate();
      }
      Serial.println(menuOpen ? "menu open" : "menu close");
    }
  }
  if (M5.BtnA.wasReleased()) {
    if (!btnALong && !swallowBtnA) {
      if (awaitingPromptClear) {
        // Ignore duplicate presses while the host clears the sent prompt.
      } else if (inPrompt) {
        if (tama.nPending > 0 && strcmp(tama.pending[0].kind, "single_choice") == 0 && tama.pending[0].nOptions > 0) {
          PendingDecision& d = tama.pending[0];
          sendAnswerChoice(d.id, d.options[d.selected].id);
        } else if (tama.nPending > 0 && strcmp(tama.pending[0].kind, "free_text_required") == 0 && tama.pending[0].nOptions > 0) {
          PendingDecision& d = tama.pending[0];
          sendAnswerChoice(d.id, d.options[d.selected].id);
        } else if (tama.nPending > 0 && strcmp(tama.pending[0].kind, "multi_choice") == 0 && tama.pending[0].nOptions > 0) {
          PendingDecision& d = tama.pending[0];
          d.options[d.selected].selected = !d.options[d.selected].selected;
          toneUiClick();
        } else if (tama.nPending > 0
            && (strcmp(tama.pending[0].kind, "notice") == 0
                || strcmp(tama.pending[0].kind, "free_text_required") == 0)) {
          PendingDecision& d = tama.pending[0];
          sendFocusSession(d.sid);
          toneFocusAck();
        } else {
          sendPermissionDecision(tama.promptId, "once");
          uint32_t tookS = (millis() - promptArrivedMs) / 1000;
          statsOnApproval(tookS);
          if (tookS < 5) triggerOneShot(P_HEART, 2000);
        }
        if (!(tama.nPending > 0
            && ((strcmp(tama.pending[0].kind, "multi_choice") == 0 && tama.pending[0].nOptions > 0)
                || strcmp(tama.pending[0].kind, "notice") == 0
                || (strcmp(tama.pending[0].kind, "free_text_required") == 0 && tama.pending[0].nOptions == 0)))) {
          responseSent = true;
          responseSentMs = millis();
          toneAnswerSent();
        }
      } else if (displayMode == DISP_SESSIONS && tama.nSessions > 0) {
        if (sessionPage >= tama.nSessions) sessionPage = 0;
        sendFocusSession(tama.sessions[sessionPage].sid);
        displayMode = DISP_SESSION;
        applyDisplayMode();
      } else if (resetOpen) {
        toneUiClick();
        resetSel = (resetSel + 1) % RESET_N;
        resetConfirmIdx = 0xFF;
      } else if (settingsOpen) {
        toneUiClick();
        settingsSel = (settingsSel + 1) % SETTINGS_N;
      } else if (menuOpen) {
        toneUiClick();
        menuSel = (menuSel + 1) % MENU_N;
      } else {
        toneUiClick();
        displayMode = (displayMode + 1) % DISP_COUNT;
        applyDisplayMode();
      }
    }
    btnALong = false;
    swallowBtnA = false;
  }

  if (M5.BtnB.pressedFor(600) && !btnBLong && !swallowBtnB) {
    btnBLong = true;
    micStartRecording();
  }

  // BtnB: prompt navigation / paging / mic hold
  if (M5.BtnB.wasReleased()) {
    if (btnBLong) {
      if (micRecording) micStopRecording(false);
    } else if (swallowBtnB) {
      swallowBtnB = false;
    } else if (awaitingPromptClear) {
      // Ignore duplicate presses while the host clears the sent prompt.
    } else if (inPrompt) {
      if (tama.nPending > 0
          && (strcmp(tama.pending[0].kind, "single_choice") == 0
              || strcmp(tama.pending[0].kind, "multi_choice") == 0
              || (strcmp(tama.pending[0].kind, "free_text_required") == 0 && tama.pending[0].nOptions > 0))
          && tama.pending[0].nOptions > 0) {
        PendingDecision& d = tama.pending[0];
        d.selected = (d.selected + 1) % d.nOptions;
        toneUiClick();
      } else if (tama.nPending > 0
             && (strcmp(tama.pending[0].kind, "notice") == 0
                 || strcmp(tama.pending[0].kind, "free_text_required") == 0)) {
        toneUiClick();
      } else {
        sendPermissionDecision(tama.promptId, "deny");
        responseSent = true;
        responseSentMs = millis();
        statsOnDenial();
        toneDenied();
      }
    } else if (displayMode == DISP_SESSIONS && tama.nSessions > 0) {
      toneUiClick();
      sessionPage = (sessionPage + 1) % tama.nSessions;
      applyDisplayMode();
    } else if (resetOpen) {
      toneUiClick();
      applyReset(resetSel);
    } else if (settingsOpen) {
      toneUiClick();
      applySetting(settingsSel);
    } else if (menuOpen) {
      toneUiClick();
      menuConfirm();
    } else if (eventVisible()) {
      tama.event.active = false;
      sendCmd("{\"cmd\":\"event_dismiss\",\"sid\":\"\"}");
      toneUiClick();
    } else if (displayMode == DISP_INFO) {
      toneUiClick();
      infoPage = (infoPage + 1) % INFO_PAGES;
    } else if (displayMode == DISP_PET) {
      toneUiClick();
      petPage = (petPage + 1) % PET_PAGES;
      applyDisplayMode();
    } else {
      toneUiClick();
      msgScroll = (msgScroll >= 30) ? 0 : msgScroll + 1;
    }
    btnBLong = false;
    swallowBtnB = false;
  }

  // blink bookkeeping

  // Charging clock: takes over the home screen when on USB power, no
  // overlays, no prompt, no live Claude data, and the RTC has been set
  // by the bridge. Pet sleeps underneath. Exit restores Y via
  // applyDisplayMode() so the next mode-switch isn't visually offset.
  clockRefreshRtc();   // 1Hz internal throttle; also caches _onUsb
  // Show the clock when nothing is happening — bridge heartbeat alone
  // doesn't count as activity (it's the only way to get the RTC synced).
  bool clocking = displayMode == DISP_NORMAL
               && !menuOpen && !settingsOpen && !resetOpen && !inPrompt
               && tama.sessionsRunning == 0 && tama.sessionsWaiting == 0
               && dataRtcValid() && _clkHwOk && _onUsb;
  if (clocking) clockUpdateOrient();
  else { clockOrient = 0; orientFrames = 0; paintedOrient = 0; }
  bool landscapeClock = clocking && clockOrient != 0;

  static bool wasClocking = false;
  static bool wasLandscape = false;
  if (clocking != wasClocking || landscapeClock != wasLandscape) {
    if (clocking && !landscapeClock) characterSetPeek(true);
    else applyDisplayMode();
    characterInvalidate();
    if (buddyMode) buddyInvalidate();
    wasClocking = clocking;
    wasLandscape = landscapeClock;
  }

  micTick();
  if (clocking) {
    uint8_t dow = clockDow();
    bool weekend = (dow == 0 || dow == 6);
    bool friday  = (dow == 5);

    uint8_t h = _clkTm.hours;
    if (h >= 1 && h < 7)             activeState = P_SLEEP;
    else if (weekend)                activeState = (now/8000 % 6 == 0) ? P_HEART : P_SLEEP;
    else if (h < 9)                  activeState = (now/6000 % 4 == 0) ? P_IDLE  : P_SLEEP;
    else if (h == 12)                activeState = (now/5000 % 3 == 0) ? P_HEART : P_IDLE;
    else if (friday && h >= 15)      activeState = (now/4000 % 3 == 0) ? P_CELEBRATE : P_IDLE;
    else if (h >= 22 || h == 0)      activeState = (now/7000 % 3 == 0) ? P_DIZZY : P_SLEEP;
    else                             activeState = (now/10000 % 5 == 0) ? P_SLEEP : P_IDLE;
  }

  static uint32_t lastPasskey = 0;
  uint32_t pk = blePasskey();
  if (pk && !lastPasskey) { wake(); tonePairing(); }
  lastPasskey = pk;

  if (napping || screenOff || landscapeClock) {
    // skip sprite render — face-down, powered off, or landscape clock
    // (which draws direct-to-LCD below)
  } else if (buddyMode) {
    buddyTick(activeState);
  } else if (characterLoaded()) {
    characterSetState(activeState);
    characterTick();
  } else {
    const Palette& p = characterPalette();
    spr.fillSprite(p.bg);
    spr.setTextColor(p.textDim, p.bg);
    spr.setTextSize(1);
    if (xferActive()) {
      uint32_t done = xferProgress(), total = xferTotal();
      spr.setCursor(8, 90);
      spr.print("installing");
      spr.setCursor(8, 102);
      spr.printf("%luK / %luK", done/1024, total/1024);
      int barW = W - 16;
      spr.drawRect(8, 116, barW, 8, p.textDim);
      if (total > 0) {
        int fill = (int)((uint64_t)barW * done / total);
        if (fill > 1) spr.fillRect(9, 117, fill - 1, 6, p.body);
      }
    } else {
      spr.setCursor(8, 100);
      spr.print("no character loaded");
    }
  }
  if (landscapeClock) {
    drawClock();
  } else if (!napping && !screenOff) {
    if (blePasskey()) drawPasskey();
    else if (clocking) drawClock();
    else if (displayMode == DISP_INFO) drawInfo();
    else if (displayMode == DISP_PET) drawPet();
    else if (displayMode == DISP_SESSION) drawFocusedSession();
    else if (displayMode == DISP_SESSIONS) drawSessionList();
    else if (settings().hud) drawHUD();
    if (micRecording) drawMicOverlay();
    if (eventVisible()) drawEventOverlay();
    if (resetOpen) drawReset();
    else if (settingsOpen) drawSettings();
    else if (menuOpen) drawMenu();
    // Attention indicator: 4px red rings hugging the screen edge. Drawn
    // last so overlays (menu/settings) stay below, and kept thin enough
    // that the 96px-wide pet sprite centered at CX is never clipped.
    if (alertBorderActive) {
      for (int i = 0; i < 4; i++) spr.drawRect(i, i, W - 2*i, H - 2*i, HOT);
    }
    spr.pushSprite(0, 0);
  }

  // Face-down nap: dim immediately, pause animations, accumulate sleep time.
  // Skipped during approval — you're holding it to read, not sleeping it.
  // Exit needs sustained not-down so IMU noise at the threshold doesn't
  // bounce brightness between 8 and full every few frames.
  static int8_t faceDownFrames = 0;
  if (!inPrompt) {
    bool down = isFaceDown();
    if (down)       { if (faceDownFrames < 20) faceDownFrames++; }
    else            { if (faceDownFrames > -10) faceDownFrames--; }
  }

  if (!napping && faceDownFrames >= 15) {
    napping = true;
    napStartMs = now;
    M5.Display.setBrightness(20);
    dimmed = true;
  } else if (napping && faceDownFrames <= -8) {
    napping = false;
    statsOnNapEnd((now - napStartMs) / 1000);
    statsOnWake();
    wake();
  }

  // millis() not the cached `now`: wake() runs after `now` is captured,
  // so now - lastInteractMs underflows when a button is held → flicker.
  // No auto-off on USB power — clock face wants to stay visible while charging.
  if (!screenOff && !inPrompt && !_onUsb
      && millis() - lastInteractMs > SCREEN_OFF_MS) {
    M5.Display.sleep();
    screenOff = true;
  }

  delay(screenOff ? 100 : 16);
}
