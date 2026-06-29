#pragma once
#include <ctype.h>
#include <string.h>

// Map bridge session `model` to a stable IDE label (matches app resolveIdeKind).
static inline const char* resolveIdeLabel(const char* model) {
  if (!model || !model[0]) return "IDE";
  char m[24];
  size_t i = 0;
  for (; model[i] && i < sizeof(m) - 1; i++) {
    m[i] = (char)tolower((unsigned char)model[i]);
  }
  m[i] = 0;
  if (strstr(m, "trae")) return "Trae";
  if (strstr(m, "cursor")) return "Cursor";
  if (strstr(m, "claude") || strstr(m, "codex")) return "Claude";
  return "IDE";
}
