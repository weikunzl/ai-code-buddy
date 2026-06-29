import { buildHomeBanner } from "./homeBanner";
import type { BuddySnapshot } from "@protocol/index";

const t = (key: string, opts?: Record<string, unknown>) => {
  if (key === "home.waitingApproval") return `需要审批：${opts?.tool}`;
  if (key === "home.activeProject") return `${opts?.project} · ${opts?.branch}`;
  if (key === "ides.cursor") return "Cursor";
  if (key === "common.main") return "main";
  if (key === "common.session") return "session";
  if (key === "home.watching") return "正在监听会话…";
  return key;
};

const baseSnap: BuddySnapshot = {
  type: "snapshot",
  total: 1,
  running: 1,
  waiting: 0,
};

test("pending does not repeat tool in subtitle", () => {
  const banner = buildHomeBanner(t, {
    connected: true,
    connecting: false,
    reconnectGaveUp: false,
    snapshot: baseSnap,
    pending: { id: "p1", sid: "s1", kind: "permission", title: "Bash", body: "ls" },
    contextSession: {
      sid: "s1",
      project: "buddy",
      branch: "main",
      phase: "waiting",
      model: "cursor",
    },
  });
  expect(banner.title).toBe("需要审批：Bash");
  expect(banner.subtitle).toBe("buddy · main · Cursor");
  expect(banner.subtitle).not.toContain("Bash");
});

test("live session separates project and ide activity", () => {
  const banner = buildHomeBanner(t, {
    connected: true,
    connecting: false,
    reconnectGaveUp: false,
    snapshot: { ...baseSnap, assistant_msg: "$ npm test" },
    pending: null,
    contextSession: {
      sid: "s1",
      project: "buddy",
      branch: "main",
      phase: "running",
      model: "cursor",
      last: "$ npm test",
    },
  });
  expect(banner.title).toBe("buddy · main");
  expect(banner.subtitle).toBe("Cursor · $ npm test");
});

test("idle session shows project and ide only", () => {
  const banner = buildHomeBanner(t, {
    connected: true,
    connecting: false,
    reconnectGaveUp: false,
    snapshot: baseSnap,
    pending: null,
    contextSession: {
      sid: "s1",
      project: "buddy",
      branch: "main",
      phase: "idle",
      model: "cursor",
      last: "connected",
    },
  });
  expect(banner.title).toBe("buddy · main");
  expect(banner.subtitle).toBe("Cursor");
});
