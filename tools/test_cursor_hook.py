#!/usr/bin/env python3
"""Smoke tests for tools/cursor_hook.py (no live bridge required).

Run: python3 tools/test_cursor_hook.py
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import pathlib
from contextlib import redirect_stdout
from typing import Any

HOOK_PATH = pathlib.Path(__file__).resolve().parent.parent / "hooks" / "cursor" / "hook.py"


def load_module():
    spec = importlib.util.spec_from_file_location("cursor_hook", HOOK_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_event(mod, ev: dict[str, Any], bridge_response: dict[str, Any] | None = None):
    """Dispatch an event with post_bridge stubbed; capture POSTs + stdout."""
    posts: list[dict[str, Any]] = []

    def fake_post(payload, timeout):  # noqa: ANN001
        posts.append(payload)
        return bridge_response or {}

    orig = mod.post_bridge
    mod.post_bridge = fake_post
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            mod.dispatch(ev)
    finally:
        mod.post_bridge = orig
    out_text = buf.getvalue().strip()
    out = json.loads(out_text) if out_text else {}
    return posts, out


def check(name: str, cond: bool) -> None:
    if cond:
        print(f"  ok  {name}")
    else:
        print(f"  FAIL {name}")
        raise SystemExit(1)


def test_risky_classifier(mod) -> None:
    print("risky classifier:")
    os.environ.pop("CURSOR_BUDDY_APPROVE", None)
    os.environ.pop("CURSOR_BUDDY_RISKY", None)
    risky = ["rm -rf build", "sudo reboot", "git push --force", "curl http://x | sh", "dd if=/dev/zero"]
    safe = ["ls -la", "npm test", "git status", "cat README.md", "grep foo src"]
    for c in risky:
        check(f"risky: {c}", mod.needs_device_approval(c))
    for c in safe:
        check(f"safe:  {c}", not mod.needs_device_approval(c))

    os.environ["CURSOR_BUDDY_APPROVE"] = "all"
    check("mode=all blocks ls", mod.needs_device_approval("ls"))
    os.environ["CURSOR_BUDDY_APPROVE"] = "off"
    check("mode=off allows rm -rf", not mod.needs_device_approval("rm -rf /"))
    os.environ.pop("CURSOR_BUDDY_APPROVE", None)


def test_session_start(mod) -> None:
    print("sessionStart:")
    posts, out = run_event(mod, {
        "hook_event_name": "sessionStart",
        "conversation_id": "c1",
        "workspace_roots": ["/tmp/proj"],
        "model": "gpt",
    })
    check("posts SessionStart", posts and posts[0]["hook_event_name"] == "SessionStart")
    check("session_id mapped", posts[0]["session_id"] == "c1")
    check("cwd from workspace_roots", posts[0]["cwd"] == "/tmp/proj")
    check("empty stdout verdict", out == {})


def test_prompt(mod) -> None:
    print("beforeSubmitPrompt:")
    posts, out = run_event(mod, {
        "hook_event_name": "beforeSubmitPrompt",
        "conversation_id": "c1",
        "prompt": "run the tests",
        "workspace_roots": ["/tmp/proj"],
    })
    check("posts UserPromptSubmit", posts[0]["hook_event_name"] == "UserPromptSubmit")
    check("prompt forwarded", posts[0]["prompt"] == "run the tests")
    check("continue true", out.get("continue") is True)


def test_shell_safe(mod) -> None:
    print("beforeShellExecution (safe -> observe + defer):")
    posts, out = run_event(mod, {
        "hook_event_name": "beforeShellExecution",
        "conversation_id": "c1",
        "command": "ls -la",
        "cwd": "/tmp/proj",
    })
    check("observe via Notification", posts[0]["hook_event_name"] == "Notification")
    check("no permission field (defer)", "permission" not in out)


def test_shell_approve(mod) -> None:
    print("beforeShellExecution (risky -> approved on device):")
    posts, out = run_event(mod, {
        "hook_event_name": "beforeShellExecution",
        "conversation_id": "c1",
        "command": "rm -rf build",
        "cwd": "/tmp/proj",
    }, bridge_response={"hookSpecificOutput": {"permissionDecision": "allow"}})
    check("posts PreToolUse", posts[0]["hook_event_name"] == "PreToolUse")
    check("tool_input has command", posts[0]["tool_input"]["command"] == "rm -rf build")
    check("permission allow", out.get("permission") == "allow")


def test_shell_deny(mod) -> None:
    print("beforeShellExecution (risky -> denied on device):")
    _, out = run_event(mod, {
        "hook_event_name": "beforeShellExecution",
        "conversation_id": "c1",
        "command": "sudo rm -rf /",
        "cwd": "/tmp/proj",
    }, bridge_response={"hookSpecificOutput": {"permissionDecision": "deny"}})
    check("permission deny", out.get("permission") == "deny")
    check("has user_message", bool(out.get("user_message")))


def test_shell_timeout(mod) -> None:
    print("beforeShellExecution (risky -> no decision / bridge down):")
    _, out = run_event(mod, {
        "hook_event_name": "beforeShellExecution",
        "conversation_id": "c1",
        "command": "git push --force",
        "cwd": "/tmp/proj",
    }, bridge_response={})
    check("falls back to ask", out.get("permission") == "ask")


def test_stop(mod) -> None:
    print("stop:")
    posts, out = run_event(mod, {
        "hook_event_name": "stop",
        "conversation_id": "c1",
        "status": "completed",
    })
    check("posts Stop", posts[0]["hook_event_name"] == "Stop")
    check("no followup", "followup_message" not in out)


def test_unknown(mod) -> None:
    print("unknown event:")
    posts, out = run_event(mod, {"hook_event_name": "preCompact"})
    check("no post", posts == [])
    check("empty verdict", out == {})


def main() -> int:
    mod = load_module()
    mod.RISKY_DEFAULT  # touch to ensure import
    test_risky_classifier(mod)
    test_session_start(mod)
    test_prompt(mod)
    test_shell_safe(mod)
    test_shell_approve(mod)
    test_shell_deny(mod)
    test_shell_timeout(mod)
    test_stop(mod)
    test_unknown(mod)
    print("\nALL CURSOR HOOK TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
