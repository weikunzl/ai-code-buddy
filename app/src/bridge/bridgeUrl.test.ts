import { isValidBridgeUrl, normalizeBridgeUrl, parseBridgeUrl, buildBridgeUrl, BUDDY_WS_PORT, normalizeWsPort } from "./bridgeUrl";

test("normalizeWsPort maps legacy and HTTP ports to 19877", () => {
  expect(normalizeWsPort("9877")).toBe("19877");
  expect(normalizeWsPort("9876")).toBe("19877");
  expect(normalizeWsPort("19876")).toBe("19877");
  expect(normalizeWsPort("")).toBe("19877");
  expect(normalizeWsPort("20000")).toBe("20000");
});

test("parseBridgeUrl coerces mistaken HTTP port", () => {
  expect(parseBridgeUrl("ws://192.168.1.5:19876")).toEqual({ host: "192.168.1.5", port: "19877" });
});

test("normalize adds ws scheme and default port 19877", () => {
  expect(normalizeBridgeUrl("192.168.1.5")).toBe("ws://192.168.1.5:19877");
  expect(normalizeBridgeUrl("192.168.1.5:19877")).toBe("ws://192.168.1.5:19877");
});

test("buildBridgeUrl uses 19877 by default", () => {
  expect(buildBridgeUrl("192.168.1.5")).toBe("ws://192.168.1.5:19877");
});

test("parseBridgeUrl", () => {
  expect(parseBridgeUrl("ws://10.0.0.8:19877")).toEqual({ host: "10.0.0.8", port: "19877" });
});

test("validate ws url", () => {
  expect(isValidBridgeUrl("ws://192.168.1.5:19877")).toBe(true);
  expect(isValidBridgeUrl("")).toBe(false);
  expect(isValidBridgeUrl("ws://127.0.0.1:19877")).toBe(false);
  expect(isValidBridgeUrl("ws://localhost:19877")).toBe(false);
});
