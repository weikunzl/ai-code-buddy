import type { BuddySnapshot, PendingItem } from "@protocol/index";
import { resolveIdeI18nKey } from "./resolveIde";
import { isLiveSession, resolveContextSession, type SessionRow } from "./sessionContext";

export type HomeBanner = {
  title: string;
  subtitle?: string;
};

type TFn = (key: string, opts?: Record<string, unknown>) => string;

function joinParts(...parts: Array<string | null | undefined>): string {
  return parts.filter((p) => p && p.trim()).join(" · ");
}

function subtitleIfDistinct(title: string, subtitle?: string | null): string | undefined {
  if (!subtitle) return undefined;
  const t = title.trim();
  const s = subtitle.trim();
  if (!s || s === t || t.includes(s) || s.includes(t)) return undefined;
  return s;
}

function ideLabel(t: TFn, model?: string | null): string {
  return t(resolveIdeI18nKey(model));
}

function projectLine(t: TFn, session: SessionRow): string {
  return t("home.activeProject", {
    project: session.project ?? t("common.session"),
    branch: session.branch ?? t("common.main"),
  });
}

/** Build non-overlapping home banner title + optional subtitle. */
export function buildHomeBanner(
  t: TFn,
  opts: {
    connected: boolean;
    connecting: boolean;
    reconnectGaveUp: boolean;
    snapshot: BuddySnapshot | null;
    pending: PendingItem | null;
    contextSession: SessionRow | null;
  },
): HomeBanner {
  const { connected, connecting, reconnectGaveUp, snapshot, pending, contextSession } = opts;

  if (reconnectGaveUp) return { title: t("home.reconnectGaveUp") };
  if (connecting) return { title: t("home.connecting") };
  if (!connected) return { title: t("home.notConnected") };

  const live = contextSession && isLiveSession(contextSession.phase) ? contextSession : null;

  if (pending) {
    const title = t("home.waitingApproval", { tool: pending.title });
    const subtitle = live
      ? subtitleIfDistinct(
          title,
          joinParts(projectLine(t, live), ideLabel(t, live.model)),
        )
      : undefined;
    return { title, subtitle };
  }

  if (live?.project) {
    const title = projectLine(t, live);
    const ide = ideLabel(t, live.model);
    const activity = pickActivity(live.last, snapshot?.assistant_msg);
    const subtitle = subtitleIfDistinct(
      title,
      activity ? joinParts(ide, activity) : ide,
    );
    return { title, subtitle };
  }

  const msg = snapshot?.assistant_msg;
  if (msg && (snapshot?.total ?? 0) > 0 && msg !== "session done") {
    const ide = snapshot?.model ? ideLabel(t, snapshot.model) : null;
    const subtitle = subtitleIfDistinct(msg, ide);
    return { title: msg, subtitle };
  }

  return { title: t("home.watching") };
}

function pickActivity(last?: string | null, assistantMsg?: string | null): string | null {
  const skip = new Set(["connected", "running", "session done"]);
  if (last && !skip.has(last)) return last;
  if (assistantMsg && !skip.has(assistantMsg)) return assistantMsg;
  return null;
}

export { ideLabel, joinParts, subtitleIfDistinct, pickActivity };
