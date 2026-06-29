import { isLiveSession, resolveContextSession } from "./sessionContext";
import type { BuddySnapshot } from "@protocol/index";

test("ignores done session in context", () => {
  const snap: BuddySnapshot = {
    type: "snapshot",
    total: 0,
    running: 0,
    waiting: 0,
    sessions: [
      {
        sid: "s1",
        project: "old",
        phase: "done",
        last: "session done",
        focused: true,
      } as never,
    ],
  };
  expect(resolveContextSession(snap, null)).toBeNull();
});

test("prefers live session over done", () => {
  const snap: BuddySnapshot = {
    type: "snapshot",
    total: 1,
    running: 0,
    waiting: 0,
    sessions: [
      { sid: "done", project: "old", phase: "done", last: "session done" } as never,
      { sid: "live", project: "app", phase: "idle", model: "cursor", focused: true } as never,
    ],
  };
  expect(resolveContextSession(snap, null)?.project).toBe("app");
});

test("isLiveSession", () => {
  expect(isLiveSession("idle")).toBe(true);
  expect(isLiveSession("running")).toBe(true);
  expect(isLiveSession("done")).toBe(false);
});
