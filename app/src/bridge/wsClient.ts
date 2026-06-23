import type { BuddySnapshot, DeviceIntent } from "@protocol/index";
import { parseBridgeMessage } from "./frameParser";

export type ConnectionStatus =
  | "disconnected"
  | "connecting"
  | "connected"
  | "error";

export const RECONNECT_INTERVAL_MS = 10_000;
export const MAX_RECONNECT_ATTEMPTS = 6;
const DEFAULT_CONNECT_TIMEOUT_MS = 10_000;

export type WsClientOptions = {
  url: string;
  onSnapshot: (snap: BuddySnapshot) => void;
  onHello: (hello: { token_required: boolean }) => void;
  onConnectionChange: (status: ConnectionStatus) => void;
  onError?: (message: string) => void;
  onFrame?: () => void;
  onReconnectGiveUp?: () => void;
  connectTimeoutMs?: number;
  reconnectIntervalMs?: number;
  maxReconnectAttempts?: number;
};

export function createWsClient(opts: WsClientOptions) {
  let ws: WebSocket | null = null;
  let stopped = true;
  let autoReconnect = false;
  let failedAttempts = 0;
  let failing = false;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let connectTimer: ReturnType<typeof setTimeout> | null = null;
  const connectTimeoutMs = opts.connectTimeoutMs ?? DEFAULT_CONNECT_TIMEOUT_MS;
  const reconnectIntervalMs = opts.reconnectIntervalMs ?? RECONNECT_INTERVAL_MS;
  const maxReconnectAttempts = opts.maxReconnectAttempts ?? MAX_RECONNECT_ATTEMPTS;

  function clearReconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
  }

  function clearConnectTimer() {
    if (connectTimer) {
      clearTimeout(connectTimer);
      connectTimer = null;
    }
  }

  function closeSocket() {
    if (!ws) return;
    ws.onopen = null;
    ws.onmessage = null;
    ws.onerror = null;
    ws.onclose = null;
    ws.close();
    ws = null;
  }

  function giveUp(code: string) {
    clearReconnect();
    clearConnectTimer();
    closeSocket();
    stopped = true;
    autoReconnect = false;
    opts.onError?.(code);
    opts.onReconnectGiveUp?.();
    opts.onConnectionChange("disconnected");
  }

  function afterFailure(code: string) {
    if (failing) return;
    failing = true;
    clearConnectTimer();
    closeSocket();
    failedAttempts += 1;
    opts.onError?.(code);
    if (!autoReconnect || stopped) {
      opts.onConnectionChange("error");
      failing = false;
      return;
    }
    if (failedAttempts >= maxReconnectAttempts) {
      giveUp("reconnect_gave_up");
      failing = false;
      return;
    }
    opts.onConnectionChange("disconnected");
    failing = false;
    scheduleReconnect();
  }

  function scheduleReconnect() {
    if (stopped || !autoReconnect) return;
    clearReconnect();
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      openSocket();
    }, reconnectIntervalMs);
  }

  function armConnectTimeout() {
    clearConnectTimer();
    connectTimer = setTimeout(() => {
      connectTimer = null;
      afterFailure("connection_timeout");
    }, connectTimeoutMs);
  }

  function openSocket() {
    if (stopped || !autoReconnect) return;
    clearReconnect();
    clearConnectTimer();
    failing = false;
    opts.onConnectionChange("connecting");

    try {
      ws = new WebSocket(opts.url);
    } catch {
      afterFailure("invalid_ws_url");
      return;
    }

    armConnectTimeout();

    ws.onopen = () => {
      // Wait for hello before marking connected.
    };

    ws.onmessage = (ev) => {
      const frame = parseBridgeMessage(String(ev.data));
      if (!frame) return;
      opts.onFrame?.();
      if (frame.type === "hello") {
        clearConnectTimer();
        failedAttempts = 0;
        opts.onConnectionChange("connected");
        opts.onHello({ token_required: frame.token_required });
        return;
      }
      if (frame.type === "snapshot") {
        opts.onSnapshot(frame);
      }
    };

    ws.onerror = () => {
      if (stopped) return;
      afterFailure("ws_error");
    };

    ws.onclose = () => {
      if (stopped || failing) return;
      if (ws) {
        ws.onopen = null;
        ws.onmessage = null;
        ws.onerror = null;
        ws.onclose = null;
        ws = null;
      }
      clearConnectTimer();
      if (!autoReconnect) {
        opts.onConnectionChange("disconnected");
        return;
      }
      afterFailure("disconnected_reconnecting");
    };
  }

  function connect() {
    stopped = false;
    autoReconnect = true;
    failedAttempts = 0;
    clearReconnect();
    clearConnectTimer();
    closeSocket();
    openSocket();
  }

  function disconnect() {
    stopped = true;
    autoReconnect = false;
    failedAttempts = 0;
    clearReconnect();
    clearConnectTimer();
    closeSocket();
    opts.onConnectionChange("disconnected");
  }

  function sendIntent(intent: DeviceIntent) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify(intent));
  }

  return { connect, disconnect, sendIntent };
}
