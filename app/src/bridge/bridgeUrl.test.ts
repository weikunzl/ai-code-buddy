import { isValidBridgeUrl, normalizeBridgeUrl, parseBridgeUrl, buildBridgeUrl, BUDDY_WS_PORT } from "./bridgeUrl";

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
