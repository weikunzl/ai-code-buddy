import type { BuddySnapshot, PendingItem } from "@protocol/index";

export type SessionRow = {
  sid?: string;
  project?: string;
  branch?: string;
  phase?: string;
  model?: string;
  last?: string;
  focused?: boolean;
};

const LIVE_PHASES = new Set(["running", "waiting", "idle"]);

export function isLiveSession(phase?: string): boolean {
  return LIVE_PHASES.has(phase ?? "");
}

/** Session tied to the first pending item, else the focused live session. */
export function resolveContextSession(
  snapshot: BuddySnapshot | null,
  pending: PendingItem | null,
): SessionRow | null {
  if (!snapshot) return null;
  const sessions = (snapshot.sessions ?? []) as SessionRow[];
  const live = sessions.filter((s) => isLiveSession(s.phase));
  const sid = pending?.sid ?? snapshot.focused;
  if (sid) {
    const match = sessions.find((s) => s.sid === sid);
    if (match && isLiveSession(match.phase)) return match;
  }
  const focusedLive = live.find((s) => s.focused);
  if (focusedLive) return focusedLive;
  if (live.length > 0) return live[0];
  if ((snapshot.total ?? 0) > 0 && (snapshot.project || snapshot.model)) {
    return {
      sid: typeof snapshot.focused === "string" ? snapshot.focused : undefined,
      project: snapshot.project,
      branch: snapshot.branch,
      model: snapshot.model,
      last: snapshot.assistant_msg,
      phase: "running",
    };
  }
  return null;
}
