/** Default WebSocket port for mobile ↔ bridge (see docs/protocol/mobile-bridge.md). */
export const BUDDY_WS_PORT = 19877;

/** HTTP hook port on the computer — not used for mobile WebSocket connections. */
export const BUDDY_HTTP_PORT = 19876;

const LEGACY_WS_PORTS = new Set(["9877", "9876", "19876"]);

/** Coerce saved or mistyped ports to the mobile WebSocket default. */
export function normalizeWsPort(port: string | number | undefined): string {
  const p = String(port ?? "").trim();
  if (!p || LEGACY_WS_PORTS.has(p)) return String(BUDDY_WS_PORT);
  return p;
}

export function buildBridgeUrl(host: string, port: string | number = BUDDY_WS_PORT): string {
  const h = host.trim();
  const p = String(port).trim() || String(BUDDY_WS_PORT);
  if (!h) return "";
  return `ws://${h}:${p}`;
}

export function parseBridgeUrl(url: string): { host: string; port: string } {
  const normalized = normalizeBridgeUrl(url);
  if (!normalized) return { host: "", port: String(BUDDY_WS_PORT) };
  try {
    const u = new URL(normalized);
    return {
      host: u.hostname,
      port: normalizeWsPort(u.port || String(BUDDY_WS_PORT)),
    };
  } catch {
    return { host: "", port: String(BUDDY_WS_PORT) };
  }
}

export function normalizeBridgeUrl(raw: string): string {
  const trimmed = raw.trim();
  if (!trimmed) return "";

  if (/^wss?:\/\//i.test(trimmed)) {
    try {
      const u = new URL(trimmed);
      if (!u.port) u.port = String(BUDDY_WS_PORT);
      return u.toString();
    } catch {
      return "";
    }
  }

  // host only: 192.168.1.10
  if (/^[\d.a-zA-Z-]+$/.test(trimmed) && !trimmed.includes(":")) {
    return buildBridgeUrl(trimmed, BUDDY_WS_PORT);
  }

  // host:port without scheme: 192.168.1.10:19877
  if (/^[\d.a-zA-Z-]+:\d+$/.test(trimmed)) {
    return `ws://${trimmed}`;
  }

  return `ws://${trimmed}`;
}

export function isLoopbackHost(host: string): boolean {
  const h = host.trim().toLowerCase();
  return h === "localhost" || h === "127.0.0.1" || h === "::1" || h === "0.0.0.0";
}

export function isValidBridgeUrl(url: string): boolean {
  if (!url) return false;
  try {
    const u = new URL(url);
    if (u.protocol !== "ws:" && u.protocol !== "wss:") return false;
    if (!u.hostname) return false;
    if (isLoopbackHost(u.hostname)) return false;
    return true;
  } catch {
    return false;
  }
}
