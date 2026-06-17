import type { BuddySnapshot, DeviceIntent } from "@protocol/index";
import { parseBridgeMessage } from "./frameParser";

export type ConnectionStatus = "disconnected" | "connecting" | "connected";

export type WsClientOptions = {
  url: string;
  onSnapshot: (snap: BuddySnapshot) => void;
  onHello: (hello: { token_required: boolean }) => void;
  onConnectionChange: (status: ConnectionStatus) => void;
  onFrame?: () => void;
};

const BACKOFF_MS = [1000, 2000, 4000, 8000, 30000];

export function createWsClient(opts: WsClientOptions) {
  let ws: WebSocket | null = null;
  let stopped = false;
  let attempt = 0;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  function clearReconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
  }

  function scheduleReconnect() {
    if (stopped) return;
    clearReconnect();
    const delay = BACKOFF_MS[Math.min(attempt, BACKOFF_MS.length - 1)];
    attempt += 1;
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      openSocket();
    }, delay);
  }

  function openSocket() {
    if (stopped) return;
    clearReconnect();
    opts.onConnectionChange("connecting");
    ws = new WebSocket(opts.url);

    ws.onopen = () => {
      // wait for hello before marking connected
    };

    ws.onmessage = (ev) => {
      const frame = parseBridgeMessage(String(ev.data));
      if (!frame) return;
      opts.onFrame?.();
      if (frame.type === "hello") {
        attempt = 0;
        opts.onConnectionChange("connected");
        opts.onHello({ token_required: frame.token_required });
        return;
      }
      if (frame.type === "snapshot") {
        opts.onSnapshot(frame);
      }
    };

    ws.onerror = () => {
      ws?.close();
    };

    ws.onclose = () => {
      ws = null;
      opts.onConnectionChange("disconnected");
      scheduleReconnect();
    };
  }

  function connect() {
    stopped = false;
    attempt = 0;
    if (ws) {
      ws.close();
      ws = null;
    }
    openSocket();
  }

  function disconnect() {
    stopped = true;
    clearReconnect();
    if (ws) {
      ws.close();
      ws = null;
    }
    opts.onConnectionChange("disconnected");
  }

  function sendIntent(intent: DeviceIntent) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify(intent));
  }

  return { connect, disconnect, sendIntent };
}
