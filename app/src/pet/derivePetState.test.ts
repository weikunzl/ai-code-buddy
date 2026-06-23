import { derivePetState } from "./derivePetState";
import type { BuddySnapshot } from "@protocol/index";

const base: BuddySnapshot = {
  type: "snapshot",
  total: 1,
  running: 0,
  waiting: 0,
};

test("disconnected → sleep", () => {
  expect(derivePetState(null, false)).toBe("sleep");
});

test("waiting permission → attention", () => {
  const snap: BuddySnapshot = {
    ...base,
    waiting: 1,
    pending: [{ id: "p1", sid: "s1", kind: "permission", title: "Bash", body: "ls" }],
  };
  expect(derivePetState(snap, true)).toBe("attention");
});

test("running sessions → busy", () => {
  expect(derivePetState({ ...base, running: 1 }, true)).toBe("busy");
});

test("recent approve → heart", () => {
  const now = 10_000;
  expect(derivePetState(base, true, now - 1000, now)).toBe("heart");
});

test("complete event → celebrate", () => {
  const snap: BuddySnapshot = {
    ...base,
    event: { kind: "complete", title: "Done" },
  };
  expect(derivePetState(snap, true)).toBe("celebrate");
});

test("connected idle → idle", () => {
  expect(derivePetState(base, true)).toBe("idle");
});
