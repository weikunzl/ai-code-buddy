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

/** Session tied to the first pending item, else the focused session. */
export function resolveContextSession(
  snapshot: BuddySnapshot | null,
  pending: PendingItem | null,
): SessionRow | null {
  if (!snapshot) return null;
  const sessions = (snapshot.sessions ?? []) as SessionRow[];
  const sid = pending?.sid ?? snapshot.focused;
  if (sid) {
    const match = sessions.find((s) => s.sid === sid);
    if (match) return match;
  }
  if (snapshot.project || snapshot.model) {
    return {
      sid: typeof snapshot.focused === "string" ? snapshot.focused : undefined,
      project: snapshot.project,
      branch: snapshot.branch,
      model: snapshot.model,
      last: snapshot.assistant_msg,
    };
  }
  return sessions.find((s) => s.focused) ?? sessions[0] ?? null;
}
