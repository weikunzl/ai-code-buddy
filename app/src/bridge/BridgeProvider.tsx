import React, { createContext, useCallback, useContext, useEffect, useRef } from "react";
import type { DeviceIntent } from "@protocol/index";
import { createWsClient } from "./wsClient";
import { useConnectionStore } from "../store/connection";
import { useSnapshotStore } from "../store/snapshot";

type BridgeContextValue = {
  connect: () => void;
  disconnect: () => void;
  sendIntent: (intent: DeviceIntent) => void;
};

const BridgeContext = createContext<BridgeContextValue | null>(null);

export function BridgeProvider({ children }: { children: React.ReactNode }) {
  const bridgeUrl = useConnectionStore((s) => s.bridgeUrl);
  const setStatus = useConnectionStore((s) => s.setStatus);
  const touchFrame = useConnectionStore((s) => s.touchFrame);
  const setSnapshot = useSnapshotStore((s) => s.setSnapshot);
  const clientRef = useRef<ReturnType<typeof createWsClient> | null>(null);

  const ensureClient = useCallback(() => {
    if (clientRef.current) return clientRef.current;
    clientRef.current = createWsClient({
      url: bridgeUrl,
      onConnectionChange: setStatus,
      onFrame: touchFrame,
      onHello: () => {},
      onSnapshot: setSnapshot,
    });
    return clientRef.current;
  }, [bridgeUrl, setSnapshot, setStatus, touchFrame]);

  useEffect(() => {
    if (clientRef.current) {
      clientRef.current.disconnect();
      clientRef.current = null;
    }
  }, [bridgeUrl]);

  const connect = useCallback(() => {
    ensureClient().connect();
  }, [ensureClient]);

  const disconnect = useCallback(() => {
    clientRef.current?.disconnect();
    setSnapshot(null);
  }, [setSnapshot]);

  const sendIntent = useCallback(
    (intent: DeviceIntent) => {
      ensureClient().sendIntent(intent);
    },
    [ensureClient],
  );

  return (
    <BridgeContext.Provider value={{ connect, disconnect, sendIntent }}>
      {children}
    </BridgeContext.Provider>
  );
}

export function useBridge(): BridgeContextValue {
  const ctx = useContext(BridgeContext);
  if (!ctx) throw new Error("useBridge must be used within BridgeProvider");
  return ctx;
}
