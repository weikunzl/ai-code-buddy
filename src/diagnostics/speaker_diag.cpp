#include <M5Unified.h>

static constexpr const uint8_t kRaw8[] = {
  128, 140, 153, 165, 177, 188, 199, 208, 217, 224, 230, 235, 239, 242, 244, 244,
  244, 242, 239, 235, 230, 224, 217, 208, 199, 188, 177, 165, 153, 140, 128, 115,
  102,  90,  78,  67,  56,  47,  38,  31,  25,  20,  16,  13,  11,  11,  11,  13,
   16,  20,  25,  31,  38,  47,  56,  67,  78,  90, 102, 115, 128, 128, 128, 128,
};

static constexpr const int16_t kRaw16[] = {
       0,  3072,  6144,  8192, 10240, 12288, 14336, 16384,
   18432, 19456, 20480, 21504, 22528, 23552, 24576, 25600,
   25600, 24576, 23552, 22528, 21504, 20480, 19456, 18432,
   16384, 14336, 12288, 10240,  8192,  6144,  3072,     0,
       0, -3072, -6144, -8192,-10240,-12288,-14336,-16384,
  -18432,-19456,-20480,-21504,-22528,-23552,-24576,-25600,
  -25600,-24576,-23552,-22528,-21504,-20480,-19456,-18432,
  -16384,-14336,-12288,-10240, -8192, -6144, -3072,     0,
};

static char lastAction[32] = "boot";
static bool lastQueued = false;
static uint32_t lastWaitMs = 0;

static void drawStatus(void) {
  auto cfg = M5.Speaker.config();
  M5.Display.startWrite();
  M5.Display.fillScreen(BLACK);
  M5.Display.setTextColor(WHITE, BLACK);
  M5.Display.setTextSize(1);
  M5.Display.setCursor(4, 4);
  M5.Display.printf("speaker diag");
  M5.Display.setCursor(4, 18);
  M5.Display.printf("last: %s", lastAction);
  M5.Display.setCursor(4, 32);
  M5.Display.printf("queued: %s", lastQueued ? "yes" : "no");
  M5.Display.setCursor(4, 46);
  M5.Display.printf("wait: %lu ms", (unsigned long)lastWaitMs);
  M5.Display.setCursor(4, 60);
  M5.Display.printf("master: %u", M5.Speaker.getVolume());
  M5.Display.setCursor(4, 74);
  M5.Display.printf("ch0: %u", M5.Speaker.getChannelVolume(0));
  M5.Display.setCursor(4, 88);
  M5.Display.printf("enabled: %s", M5.Speaker.isEnabled() ? "yes" : "no");
  M5.Display.setCursor(4, 102);
  M5.Display.printf("playing: %s", M5.Speaker.isPlaying() ? "yes" : "no");
  M5.Display.setCursor(4, 116);
  M5.Display.printf("play ch: %u", (unsigned)M5.Speaker.getPlayingChannels());
  M5.Display.setCursor(4, 130);
  M5.Display.printf("cfg rate: %lu", (unsigned long)cfg.sample_rate);
  M5.Display.setCursor(4, 144);
  M5.Display.printf("cfg stereo: %s", cfg.stereo ? "yes" : "no");
  M5.Display.setCursor(4, 158);
  M5.Display.printf("cfg buzzer: %s", cfg.buzzer ? "yes" : "no");
  M5.Display.setCursor(4, 186);
  M5.Display.print("A=tone  B=raw8  HoldA=raw16");
  M5.Display.endWrite();
}

static void logStatus(const char* label) {
  auto cfg = M5.Speaker.config();
  Serial.printf(
      "[diag] %s queued=%d wait_ms=%lu master=%u ch0=%u enabled=%d playing=%d playing_ch=%u rate=%lu stereo=%d buzzer=%d\n",
      label,
      lastQueued ? 1 : 0,
      (unsigned long)lastWaitMs,
      M5.Speaker.getVolume(),
      M5.Speaker.getChannelVolume(0),
      M5.Speaker.isEnabled() ? 1 : 0,
      M5.Speaker.isPlaying() ? 1 : 0,
      (unsigned)M5.Speaker.getPlayingChannels(),
      (unsigned long)cfg.sample_rate,
      cfg.stereo ? 1 : 0,
      cfg.buzzer ? 1 : 0);
}

static void waitForPlayback(uint32_t limitMs) {
  uint32_t start = millis();
  while (M5.Speaker.isPlaying() && millis() - start < limitMs) {
    M5.update();
    delay(1);
  }
  lastWaitMs = millis() - start;
}

static void runTone(void) {
  strcpy(lastAction, "tone");
  M5.Speaker.stop();
  lastQueued = M5.Speaker.tone(1000, 200, 0, true);
  waitForPlayback(1000);
  logStatus("tone");
  drawStatus();
}

static void runRaw8(void) {
  strcpy(lastAction, "raw8");
  M5.Speaker.stop();
  lastQueued = M5.Speaker.playRaw(kRaw8, sizeof(kRaw8), 44100, false, 120, 0, true);
  waitForPlayback(1500);
  logStatus("raw8");
  drawStatus();
}

static void runRaw16(void) {
  strcpy(lastAction, "raw16");
  M5.Speaker.stop();
  lastQueued = M5.Speaker.playRaw(kRaw16, sizeof(kRaw16) / sizeof(kRaw16[0]), 44100, false, 120, 0, true);
  waitForPlayback(1500);
  logStatus("raw16");
  drawStatus();
}

void setup(void) {
  auto cfg = M5.config();
  cfg.clear_display = true;
  M5.begin(cfg);
  Serial.begin(115200);
  M5.Display.setRotation(3);
  M5.Display.setBrightness(128);
  M5.Speaker.begin();
  M5.Speaker.setVolume(255);
  M5.Speaker.setAllChannelVolume(255);
  drawStatus();
  logStatus("boot");
  delay(200);
  runTone();
  delay(300);
  runRaw8();
  delay(300);
  runRaw16();
}

void loop(void) {
  M5.update();
  if (M5.BtnA.wasHold()) {
    runRaw16();
  } else if (M5.BtnA.wasPressed()) {
    runTone();
  } else if (M5.BtnB.wasPressed()) {
    runRaw8();
  }
  delay(10);
}
