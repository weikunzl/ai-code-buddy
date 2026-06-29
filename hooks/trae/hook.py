#!/usr/bin/env python3
"""Translate TRAE IDE hook events into claude-buddy bridge payloads.

TRAE fires lifecycle hooks with `hook_event_name` on stdin JSON. This adapter
maps those events to the same internal bridge protocol used by Cursor and
Claude Code so one desk buddy reacts to every IDE at once.

Most events are observe-only. `PreToolUse` can block until the buddy returns
allow/deny, translated into TRAE's `hookSpecificOutput.permissionDecision`.

Pure stdlib (urllib) so it runs under any python3 without a venv.

Environment overrides:
  BUDDY_BRIDGE_URL / CURSOR_BUDDY_BRIDGE_URL   bridge endpoint (default http://127.0.0.1:19876)
  TRAE_BUDDY_APPROVE       off | risky | all    (default: risky)
  TRAE_BUDDY_TIMEOUT       device decision wait seconds (default: 25)
  TRAE_BUDDY_RISKY         custom risky-command regex (overrides default)
  BUDDY_BRIDGE_AUTOSTART   1 | 0  auto-start local bridge when hooks fire (default: 1)

Fail-open by design: if the bridge is down or times out, we return an empty
verdict so TRAE's normal permission flow takes over.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request
from typing import Any

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from hooks.common.client import bridge_url
from hooks.common.ensure_bridge import ensure_bridge_running

RISKY_DEFAULT = re.compile(
    r"""(?ix)
    (?:^|[\s;&|`($])
    (?:
        sudo
      | rm\b | rmdir\b
      | dd\b | mkfs | fdisk
      | shutdown | reboot | halt | poweroff
      | kill\b | pkill | killall
      | git\s+push
      | git\s+reset\s+--hard
      | git\s+clean
      | chmod\s+-R | chown\s+-R
      | curl | wget | nc\b | ncat | scp | ssh
      | npm\s+publish | yarn\s+publish | pnpm\s+publish
      | pip\s+uninstall
      | brew\s+uninstall
      | docker\s+(?:rm | rmi | system\s+prune)
      | truncate
      | >\s*/dev/
    )
    """
)

_APPROVED_UNTIL: dict[str, float] = {}
_APPROVAL_TTL_S = 120.0


def _env(name: str, default: str) -> str:
    val = os.environ.get(name)
    return val if val else default


def approve_mode() -> str:
    mode = _env("TRAE_BUDDY_APPROVE", "risky").strip().lower()
    return mode if mode in ("off", "risky", "all") else "risky"


def decision_timeout() -> float:
    try:
        return max(1.0, float(_env("TRAE_BUDDY_TIMEOUT", "25")))
    except ValueError:
        return 25.0


def risky_pattern() -> re.Pattern[str]:
    custom = os.environ.get("TRAE_BUDDY_RISKY")
    if custom:
        try:
            return re.compile(custom, re.IGNORECASE)
        except re.error:
            pass
    return RISKY_DEFAULT


def needs_device_approval(command: str) -> bool:
    mode = approve_mode()
    if mode == "off":
        return False
    if mode == "all":
        return True
    return bool(command and risky_pattern().search(command))


def _approval_key(sid: str, kind: str, detail: str) -> str:
    return f"{sid}:{kind}:{detail}"


def mark_recently_approved(sid: str, kind: str, detail: str) -> None:
    if not sid or not detail:
        return
    _APPROVED_UNTIL[_approval_key(sid, kind, detail)] = time.time() + _APPROVAL_TTL_S


def was_recently_approved(sid: str, kind: str, detail: str) -> bool:
    if not sid or not detail:
        return False
    key = _approval_key(sid, kind, detail)
    until = _APPROVED_UNTIL.get(key, 0.0)
    if until > time.time():
        return True
    _APPROVED_UNTIL.pop(key, None)
    return False


def bridge_tool_name(tool_name: str) -> str:
    if tool_name in ("RunCommand", "execute_command", "Shell", "shell"):
        return "Bash"
    if tool_name in ("write_to_file",):
        return "Write"
    if tool_name in ("replace_in_file",):
        return "Edit"
    return tool_name


def shell_command(tool_name: str, tool_input: dict[str, Any]) -> str:
    if tool_name in ("RunCommand", "execute_command", "Shell", "shell", "Bash"):
        return str(tool_input.get("command") or "")
    return ""


def is_mcp_tool(tool_name: str) -> bool:
    return tool_name.startswith("mcp__") or tool_name.lower().startswith("mcp:")


def needs_tool_approval(tool_name: str, tool_input: dict[str, Any]) -> bool:
    mode = approve_mode()
    if mode == "off":
        return False
    if mode == "all":
        return True
    command = shell_command(tool_name, tool_input)
    if command:
        return needs_device_approval(command)
    if is_mcp_tool(tool_name):
        return True
    if tool_name in ("Write", "Edit", "write_to_file", "replace_in_file"):
        return True
    return False


def trae_permission_verdict(decision: str) -> dict[str, Any]:
    if decision == "allow":
        return {
            "continue": True,
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": "Approved on DevPet",
            },
        }
    if decision == "deny":
        return {
            "continue": True,
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "Denied on DevPet",
            },
        }
    return {"continue": True}


def bridge_permission_decision(resp: dict[str, Any]) -> str:
    hso = resp.get("hookSpecificOutput")
    if isinstance(hso, dict):
        return str(hso.get("permissionDecision") or "")
    return ""


def post_bridge(payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    ensure_bridge_running()
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url=bridge_url(),
        data=data,
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
        parsed = json.loads(body)
        return parsed if isinstance(parsed, dict) else {}
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return {}


def read_stdin() -> dict[str, Any]:
    raw = sys.stdin.buffer.read()
    if not raw:
        return {}
    try:
        obj = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return obj if isinstance(obj, dict) else {}


def session_id(ev: dict[str, Any]) -> str:
    return str(ev.get("session_id") or ev.get("conversation_id") or "")


def session_cwd(ev: dict[str, Any]) -> str:
    cwd = ev.get("cwd")
    if isinstance(cwd, str) and cwd:
        return cwd
    roots = ev.get("workspace_roots")
    if isinstance(roots, list) and roots and isinstance(roots[0], str):
        return roots[0]
    return os.getcwd()


def model(ev: dict[str, Any]) -> str:
    return str(ev.get("model") or "trae")


def emit(obj: dict[str, Any] | None) -> int:
    sys.stdout.write(json.dumps(obj or {}))
    sys.stdout.write("\n")
    sys.stdout.flush()
    return 0


def observe_tool(sid: str, cwd: str, model_name: str, message: str) -> None:
    post_bridge(
        {
            "hook_event_name": "Notification",
            "observe_only": True,
            "session_id": sid,
            "cwd": cwd,
            "model": model_name,
            "message": message[:120],
        },
        timeout=2.0,
    )


def wait_for_device_approval(
    sid: str,
    cwd: str,
    model_name: str,
    tool_name: str,
    tool_input: dict[str, Any],
) -> str:
    resp = post_bridge(
        {
            "hook_event_name": "PreToolUse",
            "session_id": sid,
            "cwd": cwd,
            "model": model_name,
            "tool_name": bridge_tool_name(tool_name),
            "tool_input": tool_input,
        },
        timeout=decision_timeout() + 5.0,
    )
    return bridge_permission_decision(resp)


def on_session_start(ev: dict[str, Any]) -> int:
    post_bridge(
        {
            "hook_event_name": "SessionStart",
            "session_id": session_id(ev),
            "cwd": session_cwd(ev),
            "model": model(ev),
        },
        timeout=2.0,
    )
    return emit({"continue": True})


def on_user_prompt_submit(ev: dict[str, Any]) -> int:
    prompt = str(ev.get("prompt") or "")
    post_bridge(
        {
            "hook_event_name": "UserPromptSubmit",
            "session_id": session_id(ev),
            "cwd": session_cwd(ev),
            "model": model(ev),
            "prompt": prompt,
        },
        timeout=2.0,
    )
    return emit({"continue": True})


def on_pre_tool_use(ev: dict[str, Any]) -> int:
    tool_name = str(ev.get("tool_name") or "Tool")
    tool_input = ev.get("tool_input") if isinstance(ev.get("tool_input"), dict) else {}
    sid = session_id(ev)
    cwd = session_cwd(ev)
    model_name = model(ev)
    command = shell_command(tool_name, tool_input)

    if command and was_recently_approved(sid, "shell", command):
        return emit(trae_permission_verdict("allow"))
    if is_mcp_tool(tool_name):
        mcp_key = json.dumps(tool_input, sort_keys=True, ensure_ascii=False)[:240]
        if was_recently_approved(sid, "mcp", f"{tool_name}:{mcp_key}"):
            return emit(trae_permission_verdict("allow"))

    if not needs_tool_approval(tool_name, tool_input):
        message = f"$ {command}"[:120] if command else tool_name[:120]
        observe_tool(sid, cwd, model_name, message)
        return emit({"continue": True})

    decision = wait_for_device_approval(sid, cwd, model_name, tool_name, tool_input)
    if decision == "allow":
        if command:
            mark_recently_approved(sid, "shell", command)
        elif is_mcp_tool(tool_name):
            mcp_key = json.dumps(tool_input, sort_keys=True, ensure_ascii=False)[:240]
            mark_recently_approved(sid, "mcp", f"{tool_name}:{mcp_key}")
    if decision:
        return emit(trae_permission_verdict(decision))
    return emit({"continue": True})


def on_post_tool_use(ev: dict[str, Any]) -> int:
    tool_name = str(ev.get("tool_name") or "Tool")
    tool_response = ev.get("tool_response") if isinstance(ev.get("tool_response"), dict) else {}
    exit_code = tool_response.get("exitCode", tool_response.get("exit_code"))
    message = f"ran {tool_name}"
    if exit_code is not None:
        message += f" (exit {exit_code})"
    observe_tool(session_id(ev), session_cwd(ev), model(ev), message)
    return emit({"continue": True})


def on_stop(ev: dict[str, Any]) -> int:
    post_bridge(
        {
            "hook_event_name": "Stop",
            "session_id": session_id(ev),
            "cwd": session_cwd(ev),
            "model": model(ev),
        },
        timeout=2.0,
    )
    return emit({"continue": True})


def on_notification(ev: dict[str, Any]) -> int:
    message = str(ev.get("message") or ev.get("notification_type") or "notification")
    observe_tool(session_id(ev), session_cwd(ev), model(ev), message)
    return emit({"continue": True})


HANDLERS = {
    "SessionStart": on_session_start,
    "UserPromptSubmit": on_user_prompt_submit,
    "PreToolUse": on_pre_tool_use,
    "PostToolUse": on_post_tool_use,
    "Stop": on_stop,
    "Notification": on_notification,
}


def dispatch(ev: dict[str, Any]) -> int:
    event = str(ev.get("hook_event_name") or "")
    handler = HANDLERS.get(event)
    if handler is None:
        return emit({"continue": True})
    return handler(ev)


def main() -> int:
    return dispatch(read_stdin())


if __name__ == "__main__":
    raise SystemExit(main())
