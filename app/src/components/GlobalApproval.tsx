import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import type { DeviceIntent } from "@protocol/index";
import { useBridge } from "../bridge/BridgeProvider";
import { useConnectionStore } from "../store/connection";
import { useSnapshotStore } from "../store/snapshot";
import { ApprovalModal } from "./ApprovalModal";

function dismissOutcome(intent: DeviceIntent): "answer" | "deny" {
  if (intent.cmd === "permission" && intent.decision === "deny") return "deny";
  return "answer";
}

/** Full-screen approval overlay on every tab when pending requires action. */
export function GlobalApproval() {
  const { t } = useTranslation();
  const snapshot = useSnapshotStore((s) => s.snapshot);
  const markApproved = useSnapshotStore((s) => s.markApproved);
  const { sendIntent } = useBridge();
  const connected = useConnectionStore((s) => s.status === "connected");
  const pending = snapshot?.pending?.[0] ?? null;
  const [sendError, setSendError] = useState<string | null>(null);

  useEffect(() => {
    setSendError(null);
  }, [pending?.id]);

  return (
    <ApprovalModal
      pending={pending}
      sendError={sendError}
      onSend={(intent) => {
        const id = pending?.id;
        if (!connected || !sendIntent(intent)) {
          setSendError(t("approval.sendFailed"));
          return;
        }
        setSendError(null);
        if (id) markApproved(id, dismissOutcome(intent));
      }}
    />
  );
}
