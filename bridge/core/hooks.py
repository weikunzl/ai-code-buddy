import json
import os
import subprocess
import time
from typing import Any

from bridge.core.state import BridgeState
from bridge.core.util import _clip


def git_value(cwd: str, *args: str) -> str:
    try:
        out = subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, timeout=2, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def git_dirty(cwd: str) -> int:
    status = git_value(cwd, "status", "--porcelain")
    return sum(1 for line in status.splitlines() if line.strip())


def project_name(cwd: str) -> str:
    root = git_value(cwd, "rev-parse", "--show-toplevel") if cwd and os.path.isdir(cwd) else ""
    return os.path.basename((root or cwd or "session").rstrip("/"))


def tool_body(tool: str, tin: dict[str, Any]) -> str:
    if tool == "Bash":
        desc = _clip(tin.get("description"), 120)
        command = _clip(tin.get("command"), 220)
        return f"{desc}\n$ {command}" if desc else command
    if tool in ("Edit", "MultiEdit", "Write", "Read"):
        return _clip(tin.get("file_path"), 220)
    if tool == "WebSearch":
        return _clip(tin.get("query"), 220)
    if tool == "WebFetch":
        return _clip(tin.get("url"), 220)
    return _clip(json.dumps(tin, ensure_ascii=False), 220)


def notification_prompt(payload: dict[str, Any]) -> dict[str, Any] | None:
    raw = payload.get("prompt")
    if not isinstance(raw, dict):
        return None
    pid = _clip(raw.get("id"), 40)
    kind = _clip(raw.get("kind"), 20)
    options = raw.get("options")
    if not pid or kind not in ("single_choice", "multi_choice", "notice", "free_text_required"):
        return None
    if kind in ("single_choice", "multi_choice") and (not isinstance(options, list) or not options):
        return None
    if kind in ("notice", "free_text_required") and not isinstance(options, list):
        options = []
    title = _clip(raw.get("title") or payload.get("message") or kind, 40)
    body = _clip(raw.get("body") or payload.get("message") or "", 240)
    return {
        "id": pid,
        "kind": kind,
        "title": title,
        "body": body,
        "options": options,
    }


def await_pending_decision(
    state: BridgeState,
    pid: str,
    deadline: float,
) -> Any:
    while time.time() < deadline:
        with state.lock:
            if pid in state.decisions:
                return state.decisions.pop(pid)
        time.sleep(0.05)
    return ""


def apply_hook(
    state: BridgeState,
    payload: dict[str, Any],
    now: int | None = None,
    wait_for_decision: bool = True,
    decision_timeout: float = 30.0,
    on_state_change: Any = None,
) -> dict[str, Any]:
    def notify_state_change() -> None:
        if on_state_change:
            on_state_change()

    now = int(now if now is not None else time.time())
    event = str(payload.get("hook_event_name") or "")
    sid = str(payload.get("session_id") or f"local_{now}")
    cwd = str(payload.get("cwd") or os.getcwd())
    project = project_name(cwd)
    branch = git_value(cwd, "rev-parse", "--abbrev-ref", "HEAD") or ""
    dirty = git_dirty(cwd)
    model = _clip(payload.get("model") or "codex", 24)

    if event in ("SessionStart", "UserPromptSubmit"):
        prompt = _clip(payload.get("prompt"), 80)
        state.upsert_session(sid, cwd, project, branch, dirty, "running", model, prompt or "running", now)
        notify_state_change()
        return {}

    if event == "Stop":
        state.clear_pending_for_session(sid)
        state.upsert_session(sid, cwd, project, branch, dirty, "done", model, "session done", now)
        with state.lock:
            state.set_event({
                "kind": "complete",
                "sid": sid,
                "title": "Done",
                "text": project or "Session complete",
                "ttl_ms": 5000,
            })
        notify_state_change()
        return {}

    if event == "Notification":
        message = _clip(payload.get("message"), 120)
        prompt = notification_prompt(payload)
        if prompt:
            state.upsert_session(sid, cwd, project, branch, dirty, "waiting", model, prompt["title"], now)
            state.add_pending(prompt["id"], sid, prompt["kind"], prompt["title"], prompt["body"], prompt["options"], now)
            notify_state_change()
            if not wait_for_decision:
                return {}
            if prompt["kind"] == "notice":
                return {}
            if prompt["kind"] == "free_text_required" and not prompt["options"]:
                return {}
            decision = await_pending_decision(state, prompt["id"], time.time() + decision_timeout)
            state.resolve_pending(prompt["id"])
            notify_state_change()
            if prompt["kind"] in ("single_choice", "free_text_required") and isinstance(decision, str) and decision:
                return {"decision": decision}
            if prompt["kind"] == "multi_choice" and isinstance(decision, list) and decision:
                return {"choices": decision}
            return {}
        lower = message.lower()
        phase = "waiting" if "waiting" in lower or "permission" in lower else "running"
        state.upsert_session(sid, cwd, project, branch, dirty, phase, model, message, now)
        notify_state_change()
        return {}

    if event == "PreToolUse":
        if payload.get("permission_mode") == "bypassPermissions":
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": "bypass-permissions mode",
                }
            }
        tool = str(payload.get("tool_name") or "Tool")
        tin = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
        pid = f"req_{int(time.time() * 1000)}_{os.getpid()}"
        state.upsert_session(sid, cwd, project, branch, dirty, "waiting", model, tool, now)
        state.add_pending(pid, sid, "permission", tool, tool_body(tool, tin), [], now)
        notify_state_change()
        if not wait_for_decision:
            return {}
        decision = await_pending_decision(state, pid, time.time() + decision_timeout)
        state.resolve_pending(pid)
        notify_state_change()
        if decision == "once":
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": "Approved on StickS3",
                }
            }
        if decision == "deny":
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": "Denied on StickS3",
                }
            }
        return {}

    return {}
