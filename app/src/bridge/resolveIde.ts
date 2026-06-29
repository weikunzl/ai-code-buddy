export type IdeKind = "cursor" | "claudeCode" | "trae" | "unknown";

/** Map bridge session `model` field to a stable IDE bucket. */
export function resolveIdeKind(model?: string | null): IdeKind {
  const m = String(model ?? "").trim().toLowerCase();
  if (!m) return "unknown";
  if (m.includes("trae")) return "trae";
  if (m.includes("cursor")) return "cursor";
  if (m.includes("claude") || m.includes("codex")) return "claudeCode";
  return "unknown";
}

export function resolveIdeI18nKey(model?: string | null): `ides.${IdeKind}` {
  return `ides.${resolveIdeKind(model)}`;
}
