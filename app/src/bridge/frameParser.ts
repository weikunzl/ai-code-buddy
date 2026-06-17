import type { BuddySnapshot } from "@protocol/index";

export type BridgeHello = {
  type: "hello";
  bridge_version: string;
  token_required: boolean;
};

export type BridgeFrame =
  | BridgeHello
  | BuddySnapshot
  | { type: "pong"; ts?: number }
  | { type: "event"; [key: string]: unknown };

export function parseBridgeMessage(raw: string): BridgeFrame | null {
  try {
    const obj = JSON.parse(raw) as Record<string, unknown>;
    if (!obj || typeof obj !== "object" || typeof obj.type !== "string") {
      return null;
    }
    return obj as BridgeFrame;
  } catch {
    return null;
  }
}
