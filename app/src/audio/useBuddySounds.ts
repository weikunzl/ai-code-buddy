import { useEffect, useRef } from "react";
import { playBuddySound } from "./SoundPlayer";
import { useConnectionStore } from "../store/connection";
import { useSnapshotStore } from "../store/snapshot";

/** Play arrival / completion cues when snapshot pending or event changes. */
export function useBuddySounds(): void {
  const muted = useConnectionStore((s) => s.soundsMuted);
  const pendingId = useSnapshotStore((s) => s.snapshot?.pending?.[0]?.id ?? null);
  const eventKey = useSnapshotStore((s) => {
    const ev = s.snapshot?.event;
    return ev ? `${ev.kind}:${ev.sid ?? ""}:${ev.title ?? ""}` : null;
  });
  const lastApproveAt = useSnapshotStore((s) => s.lastApproveAt);
  const lastDismissOutcome = useSnapshotStore((s) => s.lastDismissOutcome);

  const seenPending = useRef<string | null>(null);
  const seenEvent = useRef<string | null>(null);
  const seenDismiss = useRef<{ at: number; outcome: "answer" | "deny" } | null>(null);

  useEffect(() => {
    if (!pendingId || pendingId === seenPending.current) return;
    seenPending.current = pendingId;
    void playBuddySound("input_required", muted);
  }, [pendingId, muted]);

  useEffect(() => {
    if (!eventKey || eventKey === seenEvent.current) return;
    if (!eventKey.startsWith("complete:")) return;
    seenEvent.current = eventKey;
    void playBuddySound("complete", muted);
  }, [eventKey, muted]);

  useEffect(() => {
    if (!lastApproveAt) return;
    const prev = seenDismiss.current;
    if (prev && prev.at === lastApproveAt) return;
    const outcome = lastDismissOutcome ?? "answer";
    seenDismiss.current = { at: lastApproveAt, outcome };
    void playBuddySound(outcome === "deny" ? "deny" : "answer_sent", muted);
  }, [lastApproveAt, lastDismissOutcome, muted]);
}
