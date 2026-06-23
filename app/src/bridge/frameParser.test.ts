import { parseBridgeMessage } from "./frameParser";

test("parses snapshot", () => {
  const msg = parseBridgeMessage('{"type":"snapshot","total":0,"running":0,"waiting":0}');
  expect(msg?.type).toBe("snapshot");
});

test("parses hello", () => {
  const msg = parseBridgeMessage(
    '{"type":"hello","bridge_version":"0.1.0","token_required":false}',
  );
  expect(msg?.type).toBe("hello");
});

test("invalid json → null", () => {
  expect(parseBridgeMessage("not json")).toBeNull();
});
