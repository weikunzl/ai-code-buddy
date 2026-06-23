import { useEffect, useRef } from "react";
import { AppState } from "react-native";
import { useTranslation } from "react-i18next";
import {
  dismissPendingNotification,
  initBuddyNotifications,
  presentApprovalNotification,
  presentCompleteNotification,
} from "./buddyNotifications";
import { useConnectionStore } from "../store/connection";
import { useSnapshotStore } from "../store/snapshot";

/** Local notifications with sound for approvals and completion (incl. lock screen). */
export function useBuddyNotifications(): void {
  const { t } = useTranslation();
  const muted = useConnectionStore((s) => s.soundsMuted);
  const pending = useSnapshotStore((s) => s.snapshot?.pending?.[0] ?? null);
  const lastApproveAt = useSnapshotStore((s) => s.lastApproveAt);
  const event = useSnapshotStore((s) => s.snapshot?.event);
  const eventKey = useSnapshotStore((s) => {
    const ev = s.snapshot?.event;
    return ev ? `${ev.kind}:${ev.sid ?? ""}:${ev.title ?? ""}:${ev.text ?? ""}` : null;
  });

  const seenPending = useRef<string | null>(null);
  const seenEvent = useRef<string | null>(null);

  useEffect(() => {
    void initBuddyNotifications();
  }, []);

  useEffect(() => {
    if (!pending) {
      if (seenPending.current) {
        void dismissPendingNotification(seenPending.current);
        seenPending.current = null;
      }
      return;
    }
    if (pending.id === seenPending.current) return;
    seenPending.current = pending.id;
    void presentApprovalNotification(
      pending,
      t("notifications.approvalTitle"),
      pending.title,
      muted,
    );
  }, [pending, muted, t]);

  useEffect(() => {
    if (!lastApproveAt || !seenPending.current) return;
    void dismissPendingNotification(seenPending.current);
    seenPending.current = null;
  }, [lastApproveAt]);

  useEffect(() => {
    if (!eventKey || eventKey === seenEvent.current) return;
    if (!eventKey.startsWith("complete:")) return;
    seenEvent.current = eventKey;
    if (AppState.currentState === "active") return;
    void presentCompleteNotification(
      event?.title ?? t("notifications.completeTitle"),
      event?.text ?? t("notifications.completeBody"),
      muted,
    );
  }, [eventKey, event, muted, t]);
}
