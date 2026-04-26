#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>
#include "ble_bridge.h"
#include "xfer.h"

const uint8_t MAX_SESSIONS = 5;
const uint8_t MAX_PENDING = 3;
const uint8_t MAX_OPTIONS = 4;

struct SessionSummary {
  char sid[24];
  char project[40];
  char branch[32];
  char phase[16];
  char model[24];
  char last[80];
  int16_t dirty;
  uint32_t elapsedS;
  uint32_t pendingS;
  bool focused;
};

struct DecisionOption {
  char id[20];
  char label[28];
  char desc[44];
  bool selected;
};

struct PendingDecision {
  char id[40];
  char sid[24];
  char kind[20];
  char title[40];
  char body[120];
  uint32_t pendingS;
  DecisionOption options[MAX_OPTIONS];
  uint8_t nOptions;
  uint8_t selected;
};

struct ConsoleEvent {
  bool active;
  char kind[20];
  char sid[24];
  char title[40];
  char text[80];
  uint32_t ttlMs;
  uint32_t receivedMs;
};

struct TamaState {
  uint8_t  sessionsTotal;
  uint8_t  sessionsRunning;
  uint8_t  sessionsWaiting;
  bool     recentlyCompleted;
  uint32_t tokensToday;
  uint32_t lastUpdated;
  char     msg[24];
  bool     connected;
  char     lines[8][92];
  uint8_t  nLines;
  uint16_t lineGen;          // bumps when lines change — lets UI reset scroll
  char     promptId[40];     // pending permission request ID; empty = no prompt
  char     promptTool[20];
  char     promptHint[44];
  char     focused[24];
  char     project[40];
  char     branch[32];
  int16_t  dirty;
  char     model[24];
  char     assistantMsg[120];
  uint32_t budget;
  SessionSummary sessions[MAX_SESSIONS];
  uint8_t  nSessions;
  PendingDecision pending[MAX_PENDING];
  uint8_t  nPending;
  ConsoleEvent event;
  uint16_t sessionGen;
  uint16_t pendingGen;
  uint16_t eventGen;
};

// ---------------------------------------------------------------------------
// Three modes, checked in priority order:
//   demo   → auto-cycle fake scenarios every 8s, ignore live data
//   live   → JSON arrived in the last 10s over USB or BT
//   asleep → no data, all zeros, "No Claude connected"
// ---------------------------------------------------------------------------

static uint32_t _lastLiveMs = 0;
static uint32_t _lastBtByteMs = 0;   // hasClient() lies; track actual BT traffic
static bool     _demoMode   = false;
static uint8_t  _demoIdx    = 0;
static uint32_t _demoNext   = 0;

struct _Fake { const char* n; uint8_t t,r,w; bool c; uint32_t tok; };
static const _Fake _FAKES[] = {
  {"asleep",0,0,0,false,0}, {"one idle",1,0,0,false,12000},
  {"busy",4,3,0,false,89000}, {"attention",2,1,1,false,45000},
  {"completed",1,0,0,true,142000},
};

inline void dataSetDemo(bool on) {
  _demoMode = on;
  if (on) { _demoIdx = 0; _demoNext = millis(); }
}
inline bool dataDemo() { return _demoMode; }

inline bool dataConnected() {
  return _lastLiveMs != 0 && (millis() - _lastLiveMs) <= 30000;
}

inline bool dataBtActive() {
  // Desktop's idle keepalive is ~10s; give it 1.5x headroom.
  return _lastBtByteMs != 0 && (millis() - _lastBtByteMs) <= 15000;
}

inline const char* dataScenarioName() {
  if (_demoMode) return _FAKES[_demoIdx].n;
  if (dataConnected()) return dataBtActive() ? "bt" : "usb";
  return "none";
}

// Set true once the bridge sends a time sync — until then the RTC may
// hold whatever was on the coin cell (or 2000-01-01 if it lost power).
static bool _rtcValid = false;
inline bool dataRtcValid() { return _rtcValid; }

static void _copyField(char* dst, size_t n, const char* src) {
  if (!dst || n == 0) return;
  if (!src) src = "";
  strncpy(dst, src, n - 1);
  dst[n - 1] = 0;
}

static uint32_t _u32(JsonVariantConst v, uint32_t fallback = 0) {
  return v.is<uint32_t>() ? v.as<uint32_t>() : fallback;
}

static int16_t _i16(JsonVariantConst v, int16_t fallback = 0) {
  return v.is<int>() ? (int16_t)v.as<int>() : fallback;
}

static void _clearEvent(ConsoleEvent* ev) {
  if (!ev) return;
  ev->active = false;
  ev->kind[0] = 0;
  ev->sid[0] = 0;
  ev->title[0] = 0;
  ev->text[0] = 0;
  ev->ttlMs = 0;
}

static void _applyJson(const char* line, TamaState* out) {
  JsonDocument doc;
  if (deserializeJson(doc, line)) return;
  if (xferCommand(doc)) { _lastLiveMs = millis(); return; }

  // Bridge sends {"time":[epoch_sec, tz_offset_sec]}; gmtime_r on the
  // adjusted epoch yields local components including weekday.
  JsonArray t = doc["time"];
  if (!t.isNull() && t.size() == 2) {
    time_t local = (time_t)t[0].as<uint32_t>() + (int32_t)t[1];
    struct tm lt; gmtime_r(&local, &lt);
    M5.Rtc.setDateTime(&lt);
    extern uint32_t _clkLastRead;
    _clkLastRead = 0;   // force re-read so _clkDt and _rtcValid agree
    _rtcValid = true;
    _lastLiveMs = millis();
    return;
  }

  out->sessionsTotal     = doc["total"]     | out->sessionsTotal;
  out->sessionsRunning   = doc["running"]   | out->sessionsRunning;
  out->sessionsWaiting   = doc["waiting"]   | out->sessionsWaiting;
  out->recentlyCompleted = doc["completed"] | false;
  uint32_t bridgeTokens = doc["tokens"] | 0;
  if (doc["tokens"].is<uint32_t>()) statsOnBridgeTokens(bridgeTokens);
  out->tokensToday = doc["tokens_today"] | out->tokensToday;
  const char* m = doc["msg"];
  if (m) { strncpy(out->msg, m, sizeof(out->msg)-1); out->msg[sizeof(out->msg)-1]=0; }
  _copyField(out->focused, sizeof(out->focused), doc["focused"] | out->focused);
  _copyField(out->project, sizeof(out->project), doc["project"] | out->project);
  _copyField(out->branch, sizeof(out->branch), doc["branch"] | out->branch);
  out->dirty = _i16(doc["dirty"], out->dirty);
  _copyField(out->model, sizeof(out->model), doc["model"] | out->model);
  _copyField(out->assistantMsg, sizeof(out->assistantMsg), doc["assistant_msg"] | out->assistantMsg);
  out->budget = _u32(doc["budget"], out->budget);
  JsonArray la = doc["entries"];
  if (!la.isNull()) {
    uint8_t n = 0;
    for (JsonVariant v : la) {
      if (n >= 8) break;
      const char* s = v.as<const char*>();
      strncpy(out->lines[n], s ? s : "", 91); out->lines[n][91]=0;
      n++;
    }
    if (n != out->nLines || (n > 0 && strcmp(out->lines[n-1], out->msg) != 0)) {
      out->lineGen++;
    }
    out->nLines = n;
  }
  JsonArray sessions = doc["sessions"];
  if (!sessions.isNull()) {
    uint8_t n = 0;
    for (JsonObject s : sessions) {
      if (n >= MAX_SESSIONS) break;
      SessionSummary& ss = out->sessions[n];
      _copyField(ss.sid, sizeof(ss.sid), s["sid"] | "");
      _copyField(ss.project, sizeof(ss.project), s["project"] | s["proj"] | "");
      _copyField(ss.branch, sizeof(ss.branch), s["branch"] | "");
      _copyField(ss.phase, sizeof(ss.phase),
                 s["phase"] | (s["waiting"] ? "waiting" : s["running"] ? "running" : ""));
      _copyField(ss.model, sizeof(ss.model), s["model"] | "");
      _copyField(ss.last, sizeof(ss.last), s["last"] | "");
      ss.dirty = _i16(s["dirty"], 0);
      ss.elapsedS = _u32(s["elapsed_s"], 0);
      ss.pendingS = _u32(s["pending_s"], 0);
      ss.focused = s["focused"] | false;
      n++;
    }
    if (n != out->nSessions) out->sessionGen++;
    out->nSessions = n;
  } else if (out->nSessions != 0) {
    out->nSessions = 0;
    out->sessionGen++;
  }
  JsonArray pending = doc["pending"];
  if (!pending.isNull()) {
    char oldFirst[40];
    _copyField(oldFirst, sizeof(oldFirst), out->nPending ? out->pending[0].id : "");
    uint8_t n = 0;
    for (JsonObject p : pending) {
      if (n >= MAX_PENDING) break;
      PendingDecision& pd = out->pending[n];
      _copyField(pd.id, sizeof(pd.id), p["id"] | "");
      _copyField(pd.sid, sizeof(pd.sid), p["sid"] | "");
      _copyField(pd.kind, sizeof(pd.kind), p["kind"] | "permission");
      _copyField(pd.title, sizeof(pd.title), p["title"] | p["tool"] | "");
      _copyField(pd.body, sizeof(pd.body), p["body"] | p["hint"] | "");
      pd.pendingS = _u32(p["pending_s"], 0);
      JsonArray opts = p["options"];
      uint8_t oi = 0;
      for (JsonVariant opt : opts) {
        if (oi >= MAX_OPTIONS) break;
        DecisionOption& o = pd.options[oi];
        if (opt.is<const char*>()) {
          _copyField(o.id, sizeof(o.id), opt.as<const char*>());
          _copyField(o.label, sizeof(o.label), opt.as<const char*>());
          o.desc[0] = 0;
        } else {
          JsonObject oo = opt.as<JsonObject>();
          _copyField(o.id, sizeof(o.id), oo["id"] | oo["label"] | "");
          _copyField(o.label, sizeof(o.label), oo["label"] | oo["id"] | "");
          _copyField(o.desc, sizeof(o.desc), oo["desc"] | "");
        }
        o.selected = false;
        oi++;
      }
      pd.nOptions = oi;
      if (pd.selected >= pd.nOptions) pd.selected = 0;
      n++;
    }
    if (strcmp(oldFirst, n ? out->pending[0].id : "") != 0) {
      out->pendingGen++;
      if (n) out->pending[0].selected = 0;
    }
    out->nPending = n;
  } else if (out->nPending != 0) {
    out->nPending = 0;
    out->pendingGen++;
  }
  JsonObject pr = doc["prompt"];
  if (!pr.isNull()) {
    const char* pid = pr["id"]; const char* pt = pr["tool"]; const char* ph = pr["hint"];
    strncpy(out->promptId,   pid ? pid : "", sizeof(out->promptId)-1);   out->promptId[sizeof(out->promptId)-1]=0;
    strncpy(out->promptTool, pt  ? pt  : "", sizeof(out->promptTool)-1); out->promptTool[sizeof(out->promptTool)-1]=0;
    strncpy(out->promptHint, ph  ? ph  : "", sizeof(out->promptHint)-1); out->promptHint[sizeof(out->promptHint)-1]=0;
  } else if (out->nPending == 0) {
    out->promptId[0] = 0; out->promptTool[0] = 0; out->promptHint[0] = 0;
  }
  if (out->nPending > 0) {
    _copyField(out->promptId, sizeof(out->promptId), out->pending[0].id);
    _copyField(out->promptTool, sizeof(out->promptTool), out->pending[0].title);
    _copyField(out->promptHint, sizeof(out->promptHint), out->pending[0].body);
  }
  JsonObject ev = doc["event"];
  if (!ev.isNull()) {
    char kind[20], sid[24], title[40], text[80];
    _copyField(kind, sizeof(kind), ev["kind"] | "");
    _copyField(sid, sizeof(sid), ev["sid"] | "");
    _copyField(title, sizeof(title), ev["title"] | "");
    _copyField(text, sizeof(text), ev["text"] | "");
    uint32_t ttl = _u32(ev["ttl_ms"], 0);
    bool changed = strcmp(kind, out->event.kind) != 0
                || strcmp(sid, out->event.sid) != 0
                || strcmp(title, out->event.title) != 0
                || strcmp(text, out->event.text) != 0
                || ttl != out->event.ttlMs;
    if (changed) {
      _copyField(out->event.kind, sizeof(out->event.kind), kind);
      _copyField(out->event.sid, sizeof(out->event.sid), sid);
      _copyField(out->event.title, sizeof(out->event.title), title);
      _copyField(out->event.text, sizeof(out->event.text), text);
      out->event.ttlMs = ttl;
      out->event.receivedMs = millis();
      out->event.active = out->event.kind[0] && out->event.ttlMs > 0;
      out->eventGen++;
    }
  } else if (!out->event.active && out->event.kind[0]) {
    _clearEvent(&out->event);
  } else if (out->event.ttlMs > 0 && (millis() - out->event.receivedMs) >= out->event.ttlMs) {
    _clearEvent(&out->event);
  }
  out->lastUpdated = millis();
  _lastLiveMs = millis();
}

template<size_t N>
struct _LineBuf {
  char buf[N];
  uint16_t len = 0;
  void feed(Stream& s, TamaState* out) {
    while (s.available()) {
      char c = s.read();
      if (c == '\n' || c == '\r') {
        if (len > 0) { buf[len]=0; if (buf[0]=='{') _applyJson(buf, out); len=0; }
      } else if (len < N-1) {
        buf[len++] = c;
      }
    }
  }
};

static _LineBuf<2560> _usbLine, _btLine;

inline void dataPoll(TamaState* out) {
  uint32_t now = millis();

  if (_demoMode) {
    if (now >= _demoNext) { _demoIdx = (_demoIdx + 1) % 5; _demoNext = now + 8000; }
    const _Fake& s = _FAKES[_demoIdx];
    out->sessionsTotal=s.t; out->sessionsRunning=s.r; out->sessionsWaiting=s.w;
    out->recentlyCompleted=s.c; out->tokensToday=s.tok; out->lastUpdated=now;
    out->connected = true;
    snprintf(out->msg, sizeof(out->msg), "demo: %s", s.n);
    return;
  }

#ifndef BUDDY_BOARD_S3
  // Original StickC Plus: Serial goes through the AXP192 UART bridge and
  // is a reliable command channel. StickS3 native USB CDC reports phantom
  // bytes in Serial.available() when no host is attached, so we skip it
  // there — BLE is the primary transport anyway.
  _usbLine.feed(Serial, out);
#endif
  // BLE ring buffer is drained manually since it's not a Stream.
  while (bleAvailable()) {
    int c = bleRead();
    if (c < 0) break;
    _lastBtByteMs = millis();
    if (c == '\n' || c == '\r') {
      if (_btLine.len > 0) {
        _btLine.buf[_btLine.len] = 0;
        if (_btLine.buf[0] == '{') _applyJson(_btLine.buf, out);
        _btLine.len = 0;
      }
    } else if (_btLine.len < sizeof(_btLine.buf) - 1) {
      _btLine.buf[_btLine.len++] = (char)c;
    }
  }

  out->connected = dataConnected();
  if (!out->connected) {
    out->sessionsTotal=0; out->sessionsRunning=0; out->sessionsWaiting=0;
    out->recentlyCompleted=false; out->lastUpdated=now;
    strncpy(out->msg, "No Claude connected", sizeof(out->msg)-1);
    out->msg[sizeof(out->msg)-1]=0;
  }
}
