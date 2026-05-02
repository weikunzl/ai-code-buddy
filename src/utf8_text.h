#pragma once

#include <stddef.h>
#include <stdint.h>
#include <string.h>

static inline bool utf8IsAsciiSpace(char c) {
  return c == ' ' || c == '\t' || c == '\r';
}

static inline size_t utf8CharBytes(const char* s) {
  if (!s || !*s) return 0;
  uint8_t c0 = (uint8_t)s[0];
  if (c0 < 0x80) return 1;
  size_t need = 1;
  if ((c0 & 0xE0) == 0xC0) need = 2;
  else if ((c0 & 0xF0) == 0xE0) need = 3;
  else if ((c0 & 0xF8) == 0xF0) need = 4;
  else return 1;
  for (size_t i = 1; i < need; i++) {
    uint8_t cx = (uint8_t)s[i];
    if (cx == 0 || (cx & 0xC0) != 0x80) return 1;
  }
  return need;
}

static inline uint32_t utf8Decode(const char* s, size_t* bytesOut = nullptr) {
  size_t n = utf8CharBytes(s);
  if (bytesOut) *bytesOut = n;
  if (!s || !*s) return 0;
  if (n == 1) return (uint8_t)s[0];
  if (n == 2) {
    return ((uint32_t)(s[0] & 0x1F) << 6)
         |  (uint32_t)(s[1] & 0x3F);
  }
  if (n == 3) {
    return ((uint32_t)(s[0] & 0x0F) << 12)
         | ((uint32_t)(s[1] & 0x3F) << 6)
         |  (uint32_t)(s[2] & 0x3F);
  }
  return ((uint32_t)(s[0] & 0x07) << 18)
       | ((uint32_t)(s[1] & 0x3F) << 12)
       | ((uint32_t)(s[2] & 0x3F) << 6)
       |  (uint32_t)(s[3] & 0x3F);
}

static inline uint8_t utf8DisplayWidthCp(uint32_t cp) {
  if (cp == 0) return 0;
  if (cp < 0x20 || (cp >= 0x7F && cp < 0xA0)) return 0;
  if ((cp >= 0x0300 && cp <= 0x036F)
      || (cp >= 0x1AB0 && cp <= 0x1AFF)
      || (cp >= 0x1DC0 && cp <= 0x1DFF)
      || (cp >= 0x20D0 && cp <= 0x20FF)
      || (cp >= 0xFE20 && cp <= 0xFE2F)) {
    return 0;
  }
  if ((cp >= 0x1100 && cp <= 0x115F)
      || (cp >= 0x2329 && cp <= 0x232A)
      || (cp >= 0x2E80 && cp <= 0x303E)
      || (cp >= 0x3040 && cp <= 0x30FF)
      || (cp >= 0x3100 && cp <= 0x312F)
      || (cp >= 0x3130 && cp <= 0x318F)
      || (cp >= 0x31A0 && cp <= 0x31EF)
      || (cp >= 0x31F0 && cp <= 0x31FF)
      || (cp >= 0x3200 && cp <= 0x9FFF)
      || (cp >= 0xAC00 && cp <= 0xD7A3)
      || (cp >= 0xF900 && cp <= 0xFAFF)
      || (cp >= 0xFE10 && cp <= 0xFE19)
      || (cp >= 0xFE30 && cp <= 0xFE6F)
      || (cp >= 0xFF01 && cp <= 0xFF60)
      || (cp >= 0xFFE0 && cp <= 0xFFE6)
      || (cp >= 0x1F300 && cp <= 0x1FAFF)
      || (cp >= 0x20000 && cp <= 0x3FFFD)) {
    return 2;
  }
  return 1;
}

static inline size_t utf8TrimToWholeChars(const char* src, size_t limit) {
  if (!src) return 0;
  size_t safe = 0;
  for (size_t i = 0; src[i] && i < limit; ) {
    size_t n = utf8CharBytes(src + i);
    if (n == 0 || i + n > limit) break;
    safe = i + n;
    i += n;
  }
  return safe;
}

static inline size_t utf8SafeCopy(char* dst, size_t dstSize, const char* src) {
  if (!dst || dstSize == 0) return 0;
  if (!src) src = "";
  size_t len = utf8TrimToWholeChars(src, dstSize - 1);
  memcpy(dst, src, len);
  dst[len] = 0;
  return len;
}

static inline uint8_t utf8DisplayWidth(const char* src) {
  if (!src) return 0;
  uint16_t cols = 0;
  for (const char* p = src; *p; ) {
    size_t n = 0;
    uint32_t cp = utf8Decode(p, &n);
    cols += utf8DisplayWidthCp(cp);
    p += n ? n : 1;
  }
  return cols > 255 ? 255 : (uint8_t)cols;
}

static inline uint8_t utf8SliceColumns(
    const char* src,
    char* dst,
    size_t dstSize,
    uint8_t maxCols,
    const char** next = nullptr,
    bool skipLeadingSpaces = true,
    bool breakOnSpace = true) {
  if (!dst || dstSize == 0) return 0;
  dst[0] = 0;
  if (!src || !*src || maxCols == 0) {
    if (next) *next = src ? src : "";
    return 0;
  }

  const char* p = src;
  while (*p && skipLeadingSpaces && utf8IsAsciiSpace(*p)) p++;
  if (*p == '\n') {
    if (next) *next = p + 1;
    return 0;
  }

  size_t usedBytes = 0;
  uint8_t usedCols = 0;
  const char* lastBreakSrc = nullptr;
  size_t lastBreakBytes = 0;

  while (*p) {
    if (*p == '\n') {
      p++;
      break;
    }
    size_t n = 0;
    uint32_t cp = utf8Decode(p, &n);
    uint8_t w = utf8DisplayWidthCp(cp);
    if (usedCols + w > maxCols) {
      if (breakOnSpace && lastBreakSrc && lastBreakBytes > 0) {
        usedBytes = lastBreakBytes;
        p = lastBreakSrc;
      }
      break;
    }
    if (usedBytes + n >= dstSize) break;
    if (breakOnSpace && cp == ' ') {
      lastBreakSrc = p + n;
      lastBreakBytes = usedBytes;
    }
    memcpy(dst + usedBytes, p, n);
    usedBytes += n;
    usedCols += w;
    p += n ? n : 1;
  }

  dst[usedBytes] = 0;
  if (next) *next = p;
  return usedCols;
}

static inline uint8_t utf8WrapInto(
    const char* in,
    char* out,
    size_t rowSize,
    uint8_t maxRows,
    uint8_t width,
    bool indentContinuation = true) {
  if (!in || !out || rowSize < 2 || maxRows == 0 || width == 0) return 0;
  const char* p = in;
  uint8_t rows = 0;
  while (*p && rows < maxRows) {
    char* row = out + rows * rowSize;
    size_t prefix = 0;
    if (rows > 0 && indentContinuation) {
      row[0] = ' ';
      row[1] = 0;
      prefix = 1;
    } else {
      row[0] = 0;
    }
    const char* next = p;
    utf8SliceColumns(
        p,
        row + prefix,
        rowSize - prefix,
        width - (uint8_t)prefix,
        &next,
        true,
        true);
    if (row[prefix] == 0 && *next == 0) break;
    if (row[prefix] == 0 && next == p) {
      size_t n = utf8CharBytes(p);
      if (prefix + n < rowSize) {
        memcpy(row + prefix, p, n);
        row[prefix + n] = 0;
      }
      next = p + (n ? n : 1);
    }
    p = next;
    rows++;
  }
  return rows;
}
