import { isValidBridgeUrl, normalizeBridgeUrl, parseBridgeUrl, buildBridgeUrl, BUDDY_WS_PORT } from "./bridgeUrl";

test("normalize adds ws scheme and default port 9877", () => {
  expect(normalizeBridgeUrl("192.168.1.5")).toBe("ws://192.168.1.5:9877");
  expect(normalizeBridgeUrl("192.168.1.5:9877")).toBe("ws://192.168.1.5:9877");
});

test("buildBridgeUrl uses 9877 by default", () => {
  expect(buildBridgeUrl("192.168.1.5")).toBe("ws://192.168.1.5:9877");
});

test("parseBridgeUrl", () => {
  expect(parseBridgeUrl("ws://10.0.0.8:9877")).toEqual({ host: "10.0.0.8", port: "9877" });
});

test("validate ws url", () => {
  expect(isValidBridgeUrl("ws://192.168.1.5:9877")).toBe(true);
  expect(isValidBridgeUrl("")).toBe(false);
});
