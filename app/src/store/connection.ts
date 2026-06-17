import { create } from "zustand";
import type { ConnectionStatus } from "../bridge/wsClient";

type ConnectionState = {
  status: ConnectionStatus;
  bridgeUrl: string;
  lastFrameAt: number | null;
  setStatus: (status: ConnectionStatus) => void;
  setBridgeUrl: (url: string) => void;
  touchFrame: () => void;
  reset: () => void;
};

export const useConnectionStore = create<ConnectionState>((set) => ({
  status: "disconnected",
  bridgeUrl: "ws://127.0.0.1:9877",
  lastFrameAt: null,
  setStatus: (status) => set({ status }),
  setBridgeUrl: (bridgeUrl) => set({ bridgeUrl }),
  touchFrame: () => set({ lastFrameAt: Date.now() }),
  reset: () => set({ status: "disconnected", lastFrameAt: null }),
}));
