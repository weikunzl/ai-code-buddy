import React, { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type { DeviceIntent } from "@protocol/index";
import { useBridge } from "../bridge/BridgeProvider";
import { useConnectionStore } from "../store/connection";
import { useSnapshotStore } from "../store/snapshot";
import { ApprovalModal } from "./ApprovalModal";

function dismissOutcome(intent: DeviceIntent): "answer" | "deny" {
  if (intent.cmd === "permission") {
    const d = intent.decision;
    if (d === "skip" || d === "deny") return "deny";
  }
  return "answer";
}

/** Full-screen approval overlay on every tab when pending requires action. */
export function GlobalApproval() {
  const { t } = useTranslation();
  const snapshot = useSnapshotStore((s) => s.snapshot);
  const markApproved = useSnapshotStore((s) => s.markApproved);
  const focusSession = useSnapshotStore((s) => s.focusSession);
  const { sendIntent } = useBridge();
  const connected = useConnectionStore((s) => s.status === "connected");
  const pending = snapshot?.pending?.[0] ?? null;
  const [sendError, setSendError] = useState<string | null>(null);
  const [submittingId, setSubmittingId] = useState<string | null>(null);
  const lastIntentRef = useRef<DeviceIntent | null>(null);
  const autoFocusedPendingRef = useRef<string | null>(null);

  useEffect(() => {
    setSendError(null);
    setSubmittingId(null);
    lastIntentRef.current = null;
    autoFocusedPendingRef.current = null;
  }, [pending?.id]);

  // Auto-focus the session that raised this approval prompt.
  useEffect(() => {
    const sid = pending?.sid;
    if (!connected || !sid || !pending?.id) return;
    if (autoFocusedPendingRef.current === pending.id) return;
    autoFocusedPendingRef.current = pending.id;
    if (snapshot?.focused !== sid) {
      focusSession(sid);
      sendIntent({ cmd: "focus", sid });
    }
  }, [connected, focusSession, pending?.id, pending?.sid, sendIntent, snapshot?.focused]);

  // Wait for bridge snapshot to clear pending before dismissing — keeps pet on
  // "attention" until Cursor receives the verdict.
  useEffect(() => {
    if (!submittingId) return;
    const stillThere = snapshot?.pending?.some((p) => p.id === submittingId);
    if (stillThere) return;
    const intent = lastIntentRef.current;
    markApproved(submittingId, intent ? dismissOutcome(intent) : "answer");
    setSubmittingId(null);
    lastIntentRef.current = null;
  }, [snapshot?.pending, submittingId, markApproved]);

  return (
    <ApprovalModal
      pending={pending}
      sendError={sendError}
      onSend={(intent) => {
        const id = pending?.id;
        if (!connected || !id || !sendIntent(intent)) {
          setSendError(t("approval.sendFailed"));
          return;
        }
        setSendError(null);
        lastIntentRef.current = intent;
        setSubmittingId(id);
      }}
    />
  );
}
