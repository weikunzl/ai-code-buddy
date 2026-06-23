import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import AsyncStorage from "@react-native-async-storage/async-storage";
import type { ConnectionStatus } from "../bridge/wsClient";
import { BUDDY_WS_PORT } from "../bridge/bridgeUrl";

/** Empty until the user enters their computer's LAN IP in Settings. */
export const DEFAULT_BRIDGE_URL = "";

type ConnectionState = {
  status: ConnectionStatus;
  bridgeUrl: string;
  lastError: string | null;
  lastFrameAt: number | null;
  soundsMuted: boolean;
  reconnectGaveUp: boolean;
  setStatus: (status: ConnectionStatus) => void;
  setBridgeUrl: (url: string) => void;
  setLastError: (message: string | null) => void;
  touchFrame: () => void;
  setSoundsMuted: (muted: boolean) => void;
  setReconnectGaveUp: (value: boolean) => void;
  reset: () => void;
};

export const useConnectionStore = create(
  persist<ConnectionState>(
    (set) => ({
      status: "disconnected",
      bridgeUrl: DEFAULT_BRIDGE_URL,
      lastError: null,
      lastFrameAt: null,
      soundsMuted: false,
      reconnectGaveUp: false,
      setStatus: (status) => set({ status }),
      setBridgeUrl: (bridgeUrl) => set({ bridgeUrl }),
      setLastError: (lastError) => set({ lastError }),
      touchFrame: () => set({ lastFrameAt: Date.now() }),
      setSoundsMuted: (soundsMuted) => set({ soundsMuted }),
      setReconnectGaveUp: (reconnectGaveUp) => set({ reconnectGaveUp }),
      reset: () => set({ status: "disconnected", lastError: null, lastFrameAt: null }),
    }),
    {
      name: "buddy-connection",
      storage: createJSONStorage(() => AsyncStorage),
      partialize: (state) => ({ bridgeUrl: state.bridgeUrl, soundsMuted: state.soundsMuted }),
    },
  ),
);
