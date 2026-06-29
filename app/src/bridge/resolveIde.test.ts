import { resolveIdeI18nKey, resolveIdeKind } from "./resolveIde";

test("cursor model", () => {
  expect(resolveIdeKind("cursor")).toBe("cursor");
  expect(resolveIdeI18nKey("gpt-4-cursor")).toBe("ides.cursor");
});

test("claude code model", () => {
  expect(resolveIdeKind("codex")).toBe("claudeCode");
  expect(resolveIdeKind("claude-sonnet")).toBe("claudeCode");
});

test("trae model", () => {
  expect(resolveIdeKind("trae")).toBe("trae");
});

test("unknown model", () => {
  expect(resolveIdeKind("")).toBe("unknown");
  expect(resolveIdeKind(undefined)).toBe("unknown");
});
