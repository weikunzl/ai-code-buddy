import { create } from "zustand";
import type { BuddySnapshot } from "@protocol/index";

type SnapshotState = {
  snapshot: BuddySnapshot | null;
  lastApproveAt: number | null;
  lastDismissOutcome: "answer" | "deny" | null;
  setSnapshot: (snapshot: BuddySnapshot | null) => void;
  markApproved: (pendingId?: string, outcome?: "answer" | "deny") => void;
  focusSession: (sid: string) => void;
};

export const useSnapshotStore = create<SnapshotState>((set) => ({
  snapshot: null,
  lastApproveAt: null,
  lastDismissOutcome: null,
  setSnapshot: (snapshot) => set({ snapshot }),
  markApproved: (pendingId, outcome = "answer") =>
    set((state) => {
      const snap = state.snapshot;
      const base = {
        lastApproveAt: Date.now(),
        lastDismissOutcome: outcome,
      };
      if (!snap?.pending?.length) {
        return base;
      }
      const id = pendingId ?? snap.pending[0]?.id;
      const pending = id ? snap.pending.filter((p) => p.id !== id) : snap.pending.slice(1);
      return {
        ...base,
        snapshot: { ...snap, pending },
      };
    }),
  focusSession: (sid) =>
    set((state) => {
      const snap = state.snapshot;
      if (!snap?.sessions?.length) return {};
      const sessions = snap.sessions as Array<{
        sid?: string;
        project?: string;
        branch?: string;
        model?: string;
        last?: string;
        dirty?: number;
        focused?: boolean;
      }>;
      const target = sessions.find((s) => s.sid === sid);
      if (!target) return {};
      return {
        snapshot: {
          ...snap,
          focused: sid,
          project: target.project,
          branch: target.branch,
          model: target.model,
          assistant_msg: target.last,
          dirty: target.dirty,
          sessions: sessions.map((s) => ({ ...s, focused: s.sid === sid })),
        },
      };
    }),
}));
