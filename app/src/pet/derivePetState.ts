import type { BuddySnapshot, PetState } from "@protocol/index";

export function derivePetState(
  snapshot: BuddySnapshot | null,
  connected: boolean,
  recentApproveAt?: number,
  now = Date.now(),
): PetState {
  if (!connected) return "sleep";
  if (recentApproveAt && now - recentApproveAt < 5000) return "heart";
  const pending = snapshot?.pending?.[0];
  if (snapshot?.waiting && snapshot.waiting > 0) return "attention";
  if (pending?.kind === "permission") return "attention";
  if (snapshot?.event?.kind === "complete") return "celebrate";
  if ((snapshot?.running ?? 0) > 0) return "busy";
  return "idle";
}
