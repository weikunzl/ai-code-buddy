#!/usr/bin/env python3
"""Smoke tests for hooks/trae/hook.py (no live bridge required).

Run: python3 tools/test_trae_hook.py
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import pathlib
from contextlib import redirect_stdout
from typing import Any

HOOK_PATH = pathlib.Path(__file__).resolve().parent.parent / "hooks" / "trae" / "hook.py"


def load_module():
    spec = importlib.util.spec_from_file_location("trae_hook", HOOK_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_event(mod, ev: dict[str, Any], bridge_response: dict[str, Any] | None = None):
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
    os.environ.pop("TRAE_BUDDY_APPROVE", None)
    risky = ["rm -rf build", "sudo reboot", "git push --force"]
    safe = ["ls -la", "npm test", "git status"]
    for c in risky:
        check(f"risky: {c}", mod.needs_device_approval(c))
    for c in safe:
        check(f"safe:  {c}", not mod.needs_device_approval(c))


def test_session_start(mod) -> None:
    print("SessionStart:")
    posts, out = run_event(mod, {
        "hook_event_name": "SessionStart",
        "session_id": "s1",
        "cwd": "/tmp/proj",
    })
    check("posts SessionStart", posts[0]["hook_event_name"] == "SessionStart")
    check("continue true", out.get("continue") is True)


def test_prompt(mod) -> None:
    print("UserPromptSubmit:")
    posts, out = run_event(mod, {
        "hook_event_name": "UserPromptSubmit",
        "session_id": "s1",
        "prompt": "run tests",
        "cwd": "/tmp/proj",
    })
    check("posts UserPromptSubmit", posts[0]["hook_event_name"] == "UserPromptSubmit")
    check("prompt forwarded", posts[0]["prompt"] == "run tests")


def test_run_command_safe(mod) -> None:
    print("PreToolUse RunCommand (safe -> observe):")
    posts, out = run_event(mod, {
        "hook_event_name": "PreToolUse",
        "session_id": "s1",
        "tool_name": "RunCommand",
        "tool_input": {"command": "ls -la"},
        "cwd": "/tmp/proj",
    })
    check("observe via Notification", posts[0]["hook_event_name"] == "Notification")
    check("no permissionDecision", "hookSpecificOutput" not in out)


def test_run_command_approve(mod) -> None:
    print("PreToolUse RunCommand (risky -> allow):")
    posts, out = run_event(mod, {
        "hook_event_name": "PreToolUse",
        "session_id": "s1",
        "tool_name": "RunCommand",
        "tool_input": {"command": "rm -rf build"},
        "cwd": "/tmp/proj",
    }, bridge_response={"hookSpecificOutput": {"permissionDecision": "allow"}})
    check("posts PreToolUse", posts[0]["hook_event_name"] == "PreToolUse")
    check("maps RunCommand -> Bash", posts[0]["tool_name"] == "Bash")
    hso = out.get("hookSpecificOutput") or {}
    check("permission allow", hso.get("permissionDecision") == "allow")


def test_run_command_deny(mod) -> None:
    print("PreToolUse RunCommand (risky -> deny):")
    _, out = run_event(mod, {
        "hook_event_name": "PreToolUse",
        "session_id": "s1",
        "tool_name": "RunCommand",
        "tool_input": {"command": "sudo rm -rf /"},
        "cwd": "/tmp/proj",
    }, bridge_response={"hookSpecificOutput": {"permissionDecision": "deny"}})
    hso = out.get("hookSpecificOutput") or {}
    check("permission deny", hso.get("permissionDecision") == "deny")


def test_legacy_execute_command(mod) -> None:
    print("PreToolUse execute_command (legacy name):")
    posts, _ = run_event(mod, {
        "hook_event_name": "PreToolUse",
        "session_id": "s1",
        "tool_name": "execute_command",
        "tool_input": {"command": "git push"},
        "cwd": "/tmp/proj",
    }, bridge_response={"hookSpecificOutput": {"permissionDecision": "allow"}})
    check("posts PreToolUse", posts[0]["hook_event_name"] == "PreToolUse")
    check("maps to Bash", posts[0]["tool_name"] == "Bash")


def test_stop(mod) -> None:
    print("Stop:")
    posts, out = run_event(mod, {
        "hook_event_name": "Stop",
        "session_id": "s1",
        "cwd": "/tmp/proj",
    })
    check("posts Stop", posts[0]["hook_event_name"] == "Stop")
    check("continue true", out.get("continue") is True)


def test_install_format() -> None:
    print("install.py nested format:")
    install_path = pathlib.Path(__file__).resolve().parent.parent / "hooks" / "trae" / "install.py"
    spec = importlib.util.spec_from_file_location("trae_install", install_path)
    assert spec and spec.loader
    inst = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(inst)
    group = inst.make_group({"timeout": 60, "matcher": "RunCommand"})
    check("has nested hooks", isinstance(group.get("hooks"), list))
    check("has command", "command" in (group["hooks"][0]))
    check("has matcher", group.get("matcher") == "RunCommand")


def main() -> int:
    mod = load_module()
    test_risky_classifier(mod)
    test_session_start(mod)
    test_prompt(mod)
    test_run_command_safe(mod)
    test_run_command_approve(mod)
    test_run_command_deny(mod)
    test_legacy_execute_command(mod)
    test_stop(mod)
    test_install_format()
    print("\nALL TRAE HOOK TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
