import React from "react";
import type { DeviceIntent } from "@protocol/index";
import { useBridge } from "../bridge/BridgeProvider";
import { useSnapshotStore } from "../store/snapshot";
import { ApprovalModal } from "./ApprovalModal";

function dismissOutcome(intent: DeviceIntent): "answer" | "deny" {
  if (intent.cmd === "permission" && intent.decision === "deny") return "deny";
  return "answer";
}

/** Full-screen approval overlay on every tab when pending requires action. */
export function GlobalApproval() {
  const snapshot = useSnapshotStore((s) => s.snapshot);
  const markApproved = useSnapshotStore((s) => s.markApproved);
  const { sendIntent } = useBridge();
  const pending = snapshot?.pending?.[0] ?? null;

  return (
    <ApprovalModal
      pending={pending}
      onSend={(intent) => {
        const id = pending?.id;
        sendIntent(intent);
        if (id) markApproved(id, dismissOutcome(intent));
      }}
    />
  );
}
