#!/usr/bin/env python3
"""Translate Cursor agent hook events into claude-buddy session_bridge payloads.

The session bridge (tools/session_bridge.py) speaks one internal protocol:
Claude-Code-style `hook_event_name` payloads POSTed to a local HTTP endpoint.
This adapter lets Cursor share the very same bridge and device, so a single
desk buddy reacts to both Cursor and Claude/Codex sessions at once.

One script handles every Cursor hook event: Cursor includes `hook_event_name`
in the stdin JSON, so we dispatch on it. Most events are fire-and-forget
(observe/display only). `beforeShellExecution` can block waiting for an
approve/deny decision made on the hardware buddy and translate it back into
Cursor's `{"permission": ...}` verdict.

Pure stdlib (urllib) so it runs under any python3 without a venv.

Environment overrides:
  BUDDY_BRIDGE_URL / CURSOR_BUDDY_BRIDGE_URL   bridge endpoint (default http://127.0.0.1:19876)
  CURSOR_BUDDY_APPROVE      off | risky | all   (default: risky)
  CURSOR_BUDDY_TIMEOUT      device decision wait seconds (default: 25)
  CURSOR_BUDDY_RISKY        custom risky-command regex (overrides default)
  BUDDY_BRIDGE_AUTOSTART    1 | 0  auto-start local bridge when hooks fire (default: 1)

Fail-open by design: if the bridge is down or anything goes wrong, shell
commands are never blocked (we return an empty verdict so Cursor's normal
flow takes over). Set the hook's `failClosed: true` in hooks.json only if you
want the opposite.
"""
from __future__ import annotations

import json
import os
import re
import pathlib
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

# Commands that should require an explicit approve/deny on the hardware buddy
# when CURSOR_BUDDY_APPROVE=risky (the default). Deliberately conservative:
# clearly destructive or outbound-network commands only, so everyday commands
# keep running through Cursor's normal flow without a device round-trip.
RISKY_DEFAULT = re.compile(
    r"""(?ix)            # case-insensitive, verbose
    (?:^|[\s;&|`($])     # start, or a shell separator
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


def _env(name: str, default: str) -> str:
    val = os.environ.get(name)
    return val if val else default


def approve_mode() -> str:
    mode = _env("CURSOR_BUDDY_APPROVE", "risky").strip().lower()
    return mode if mode in ("off", "risky", "all") else "risky"


def decision_timeout() -> float:
    try:
        return max(1.0, float(_env("CURSOR_BUDDY_TIMEOUT", "25")))
    except ValueError:
        return 25.0


def risky_pattern() -> re.Pattern[str]:
    custom = os.environ.get("CURSOR_BUDDY_RISKY")
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


# Skip a second blocking hook when preToolUse already approved the same action.
_APPROVED_UNTIL: dict[str, float] = {}
_APPROVAL_TTL_S = 120.0


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
    if tool_name in ("Shell", "shell"):
        return "Bash"
    return tool_name


def shell_command(tool_name: str, tool_input: dict[str, Any]) -> str:
    if tool_name in ("Shell", "shell", "Bash"):
        return str(tool_input.get("command") or "")
    return ""


def is_mcp_tool(tool_name: str) -> bool:
    lower = tool_name.lower()
    return lower.startswith("mcp:") or lower.startswith("mcp ") or lower == "mcp"


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
    return False


def cursor_permission_verdict(decision: str) -> dict[str, Any]:
    if decision == "allow":
        return {"permission": "allow"}
    if decision == "deny":
        return {
            "permission": "deny",
            "user_message": "Denied on the hardware buddy.",
            "agent_message": "The user denied this action on the hardware buddy.",
        }
    return {"permission": "ask"}


def bridge_permission_decision(resp: dict[str, Any]) -> str:
    hso = resp.get("hookSpecificOutput")
    if isinstance(hso, dict):
        return str(hso.get("permissionDecision") or "")
    return ""


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


def observe_tool(
    sid: str,
    cwd: str,
    model_name: str,
    message: str,
) -> None:
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


def post_bridge(payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    """POST a payload to the bridge; return parsed JSON or {} on any failure."""
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
    return str(ev.get("conversation_id") or ev.get("session_id") or "")


def session_cwd(ev: dict[str, Any]) -> str:
    cwd = ev.get("cwd")
    if isinstance(cwd, str) and cwd:
        return cwd
    roots = ev.get("workspace_roots")
    if isinstance(roots, list) and roots and isinstance(roots[0], str):
        return roots[0]
    return os.getcwd()


def model(ev: dict[str, Any]) -> str:
    # Bridge/firmware use `model` as IDE bucket; Cursor puts the LLM id in this field.
    return "cursor"


def emit(obj: dict[str, Any] | None) -> int:
    sys.stdout.write(json.dumps(obj or {}))
    sys.stdout.write("\n")
    sys.stdout.flush()
    return 0


# --- per-event handlers ---------------------------------------------------


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
    return emit({})


def on_before_submit_prompt(ev: dict[str, Any]) -> int:
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
    # Never block prompt submission from the buddy.
    return emit({"continue": True})


def on_before_shell(ev: dict[str, Any]) -> int:
    command = str(ev.get("command") or "")
    sid = session_id(ev)
    cwd = session_cwd(ev)
    model_name = model(ev)

    if was_recently_approved(sid, "shell", command):
        return emit({"permission": "allow"})

    if not needs_device_approval(command):
        observe_tool(sid, cwd, model_name, f"$ {command}")
        return emit({})

    decision = wait_for_device_approval(
        sid,
        cwd,
        model_name,
        "Bash",
        {"command": command, "description": ""},
    )
    if decision == "allow":
        mark_recently_approved(sid, "shell", command)
    return emit(cursor_permission_verdict(decision))


def on_pre_tool_use(ev: dict[str, Any]) -> int:
    tool_name = str(ev.get("tool_name") or "Tool")
    tool_input = ev.get("tool_input") if isinstance(ev.get("tool_input"), dict) else {}
    sid = session_id(ev)
    cwd = session_cwd(ev)
    model_name = model(ev)
    command = shell_command(tool_name, tool_input)

    if command and was_recently_approved(sid, "shell", command):
        return emit({"permission": "allow"})
    if is_mcp_tool(tool_name):
        mcp_key = json.dumps(tool_input, sort_keys=True, ensure_ascii=False)[:240]
        if was_recently_approved(sid, "mcp", f"{tool_name}:{mcp_key}"):
            return emit({"permission": "allow"})

    if not needs_tool_approval(tool_name, tool_input):
        message = f"$ {command}"[:120] if command else tool_name[:120]
        observe_tool(sid, cwd, model_name, message)
        return emit({})

    decision = wait_for_device_approval(sid, cwd, model_name, tool_name, tool_input)
    if decision == "allow":
        if command:
            mark_recently_approved(sid, "shell", command)
        elif is_mcp_tool(tool_name):
            mcp_key = json.dumps(tool_input, sort_keys=True, ensure_ascii=False)[:240]
            mark_recently_approved(sid, "mcp", f"{tool_name}:{mcp_key}")
    return emit(cursor_permission_verdict(decision))


def on_before_mcp(ev: dict[str, Any]) -> int:
    tool_name = str(ev.get("tool_name") or ev.get("mcp_tool") or "MCP")
    tool_input = ev.get("tool_input") if isinstance(ev.get("tool_input"), dict) else {}
    if not tool_input and isinstance(ev.get("arguments"), dict):
        tool_input = ev["arguments"]
    sid = session_id(ev)
    cwd = session_cwd(ev)
    model_name = model(ev)
    mcp_key = json.dumps(tool_input, sort_keys=True, ensure_ascii=False)[:240]
    dedupe_detail = f"{tool_name}:{mcp_key}"

    if was_recently_approved(sid, "mcp", dedupe_detail):
        return emit({"permission": "allow"})

    mode = approve_mode()
    if mode == "off":
        observe_tool(sid, cwd, model_name, tool_name[:120])
        return emit({})

    decision = wait_for_device_approval(sid, cwd, model_name, tool_name, tool_input)
    if decision == "allow":
        mark_recently_approved(sid, "mcp", dedupe_detail)
    return emit(cursor_permission_verdict(decision))


def on_after_shell(ev: dict[str, Any]) -> int:
    # Observe-only commands are logged in beforeShell; skip duplicate "ran …" lines.
    return emit({})


def on_after_file_edit(ev: dict[str, Any]) -> int:
    path = str(ev.get("file_path") or "")
    name = os.path.basename(path) or path
    post_bridge(
        {
            "hook_event_name": "Notification",
            "observe_only": True,
            "session_id": session_id(ev),
            "cwd": session_cwd(ev),
            "model": model(ev),
            "message": f"edit {name}"[:120],
        },
        timeout=2.0,
    )
    return emit({})


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
    # Never auto-submit a follow-up from the buddy.
    return emit({})


HANDLERS = {
    "sessionStart": on_session_start,
    "beforeSubmitPrompt": on_before_submit_prompt,
    "preToolUse": on_pre_tool_use,
    "beforeShellExecution": on_before_shell,
    "beforeMCPExecution": on_before_mcp,
    "afterShellExecution": on_after_shell,
    "afterFileEdit": on_after_file_edit,
    "stop": on_stop,
}


def dispatch(ev: dict[str, Any]) -> int:
    event = str(ev.get("hook_event_name") or "")
    handler = HANDLERS.get(event)
    if handler is None:
        # Unknown / unmapped event: stay out of the way.
        return emit({})
    return handler(ev)


def main() -> int:
    return dispatch(read_stdin())


if __name__ == "__main__":
    raise SystemExit(main())
