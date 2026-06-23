import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import type { DeviceIntent } from "@protocol/index";
import { isValidBridgeUrl, isLoopbackHost, normalizeBridgeUrl, parseBridgeUrl } from "./bridgeUrl";
import { createWsClient } from "./wsClient";
import { useConnectionStore } from "../store/connection";
import { useSnapshotStore } from "../store/snapshot";

type BridgeContextValue = {
  connect: () => boolean;
  disconnect: () => void;
  sendIntent: (intent: DeviceIntent) => void;
};

const BridgeContext = createContext<BridgeContextValue | null>(null);

export function BridgeProvider({ children }: { children: React.ReactNode }) {
  const bridgeUrl = useConnectionStore((s) => s.bridgeUrl);
  const setStatus = useConnectionStore((s) => s.setStatus);
  const setLastError = useConnectionStore((s) => s.setLastError);
  const setReconnectGaveUp = useConnectionStore((s) => s.setReconnectGaveUp);
  const reconnectGaveUp = useConnectionStore((s) => s.reconnectGaveUp);
  const touchFrame = useConnectionStore((s) => s.touchFrame);
  const setSnapshot = useSnapshotStore((s) => s.setSnapshot);
  const clientRef = useRef<ReturnType<typeof createWsClient> | null>(null);
  const urlRef = useRef("");
  const autoStartedRef = useRef(false);
  const [storeReady, setStoreReady] = useState(
    () => useConnectionStore.persist.hasHydrated(),
  );

  useEffect(() => {
    if (useConnectionStore.persist.hasHydrated()) {
      setStoreReady(true);
      return;
    }
    return useConnectionStore.persist.onFinishHydration(() => setStoreReady(true));
  }, []);

  const ensureClient = useCallback(
    (url: string) => {
      if (clientRef.current && urlRef.current === url) {
        return clientRef.current;
      }
      clientRef.current?.disconnect();
      urlRef.current = url;
      clientRef.current = createWsClient({
        url,
        onConnectionChange: setStatus,
        onError: setLastError,
        onFrame: touchFrame,
        onHello: () => setLastError(null),
        onSnapshot: setSnapshot,
        onReconnectGiveUp: () => setReconnectGaveUp(true),
      });
      return clientRef.current;
    },
    [setLastError, setReconnectGaveUp, setSnapshot, setStatus, touchFrame],
  );

  useEffect(() => {
    clientRef.current?.disconnect();
    clientRef.current = null;
    urlRef.current = "";
    autoStartedRef.current = false;
  }, [bridgeUrl]);

  const connect = useCallback(() => {
    const url = normalizeBridgeUrl(bridgeUrl);
    if (!url) {
      setLastError("bridge_url_missing");
      setStatus("error");
      return false;
    }
    const { host } = parseBridgeUrl(url);
    if (isLoopbackHost(host)) {
      setLastError("bridge_url_loopback");
      setStatus("error");
      return false;
    }
    if (!isValidBridgeUrl(url)) {
      setLastError("invalid_bridge_url");
      setStatus("error");
      return false;
    }
    setReconnectGaveUp(false);
    setLastError(null);
    ensureClient(url).connect();
    return true;
  }, [bridgeUrl, ensureClient, setLastError, setReconnectGaveUp, setStatus]);

  const disconnect = useCallback(() => {
    clientRef.current?.disconnect();
    setSnapshot(null);
    setLastError(null);
  }, [setLastError, setSnapshot]);

  useEffect(() => {
    if (!storeReady || autoStartedRef.current || reconnectGaveUp) return;
    const url = normalizeBridgeUrl(bridgeUrl);
    if (!isValidBridgeUrl(url)) return;
    autoStartedRef.current = true;
    connect();
  }, [storeReady, reconnectGaveUp, connect, bridgeUrl]);

  const sendIntent = useCallback(
    (intent: DeviceIntent) => {
      ensureClient(urlRef.current || normalizeBridgeUrl(bridgeUrl)).sendIntent(intent);
    },
    [bridgeUrl, ensureClient],
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
