export type PetState =
  | "sleep"
  | "idle"
  | "busy"
  | "attention"
  | "celebrate"
  | "dizzy"
  | "heart";

export type PendingKind =
  | "permission"
  | "single_choice"
  | "multi_choice"
  | "notice"
  | "free_text_required";

export interface PendingItem {
  id: string;
  sid: string;
  kind: PendingKind;
  title: string;
  body: string;
  options?: Array<{ id: string; label: string; desc?: string }>;
}

export interface BuddySnapshot {
  type: "snapshot";
  total: number;
  running: number;
  waiting: number;
  msg?: string;
  entries?: string[];
  tokens?: number;
  tokens_today?: number;
  focused?: string;
  project?: string;
  branch?: string;
  dirty?: number;
  model?: string;
  assistant_msg?: string;
  sessions?: Array<Record<string, unknown>>;
  pending?: PendingItem[];
  prompt?: { id: string; tool?: string; hint?: string };
  event?: { kind: string; title?: string; text?: string; ttl_ms?: number };
}

export interface PermissionIntent {
  cmd: "permission";
  id: string;
  decision: "once" | "deny";
}

export interface AnswerIntent {
  cmd: "answer";
  id: string;
  choice?: string;
  choices?: string[];
}

export type DeviceIntent = PermissionIntent | AnswerIntent | { cmd: string; [key: string]: unknown };
