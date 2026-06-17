import { create } from "zustand";
import type { BuddySnapshot } from "@protocol/index";

type SnapshotState = {
  snapshot: BuddySnapshot | null;
  setSnapshot: (snapshot: BuddySnapshot | null) => void;
};

export const useSnapshotStore = create<SnapshotState>((set) => ({
  snapshot: null,
  setSnapshot: (snapshot) => set({ snapshot }),
}));
