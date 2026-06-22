#!/usr/bin/env python3
"""Install Claude Code desk-buddy hooks (manual snippet + optional settings patch).

Claude Code hook install paths vary by version; this script always prints a
manual ~/.claude/settings.json snippet. When settings.json already exists and
is valid JSON, it can merge buddy hook entries safely (idempotent).

Usage:
  python3 hooks/claude-code/install.py              # print snippet + patch if safe
  python3 hooks/claude-code/install.py --print    # snippet only, no write
  python3 hooks/claude-code/install.py --remove   # remove our entries
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
HOOK_SCRIPT = REPO_ROOT / "hooks" / "claude-code" / "hook.py"
SETTINGS_JSON = pathlib.Path.home() / ".claude" / "settings.json"

EVENTS = (
    "SessionStart",
    "UserPromptSubmit",
    "Stop",
    "PreToolUse",
    "Notification",
)


def hook_command() -> str:
    return f'/usr/bin/env PYTHONPATH="{REPO_ROOT}" python3 "{HOOK_SCRIPT}"'


def hook_entry() -> dict[str, object]:
    return {"type": "command", "command": hook_command()}


def snippet() -> dict:
    hooks = {event: [hook_entry()] for event in EVENTS}
    return {"hooks": hooks}


def is_ours(entry: object) -> bool:
    if not isinstance(entry, dict):
        return False
    cmd = entry.get("command")
    return isinstance(cmd, str) and str(HOOK_SCRIPT) in cmd


def load_settings() -> dict | None:
    if not SETTINGS_JSON.exists():
        return None
    try:
        data = json.loads(SETTINGS_JSON.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[install] existing settings.json is unreadable: {exc}", file=sys.stderr)
        return None
    return data if isinstance(data, dict) else {}


def strip_ours(data: dict) -> dict:
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return data
    for event in list(hooks.keys()):
        arr = hooks.get(event)
        if not isinstance(arr, list):
            continue
        kept = [e for e in arr if not is_ours(e)]
        if kept:
            hooks[event] = kept
        else:
            hooks.pop(event, None)
    return data


def add_ours(data: dict) -> dict:
    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        hooks = {}
        data["hooks"] = hooks
    cmd_entry = hook_entry()
    for event in EVENTS:
        arr = hooks.get(event)
        if not isinstance(arr, list):
            arr = []
        arr.append(cmd_entry)
        hooks[event] = arr
    return data


def print_manual_instructions() -> None:
    print("[install] Claude Code buddy hook manual settings.json snippet:")
    print(json.dumps(snippet(), indent=2))
    print(f"[install] hook script: {HOOK_SCRIPT}")
    print("[install] merge the hooks section into ~/.claude/settings.json")
    print("[install] set BUDDY_BRIDGE_URL if the bridge is not on http://127.0.0.1:9876")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--remove", action="store_true", help="uninstall buddy hooks")
    parser.add_argument("--print", dest="dry", action="store_true", help="print snippet only")
    args = parser.parse_args(argv)

    if not HOOK_SCRIPT.exists():
        print(f"[install] missing {HOOK_SCRIPT}", file=sys.stderr)
        return 1

    print_manual_instructions()

    if args.dry:
        return 0

    data = load_settings()
    if data is None:
        if args.remove:
            print("[install] no settings.json to update")
            return 0
        print("[install] skipped automatic patch (no readable ~/.claude/settings.json)")
        return 0

    data = strip_ours(data)
    if not args.remove:
        data = add_ours(data)

    SETTINGS_JSON.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_JSON.write_text(json.dumps(data, indent=2) + "\n", "utf-8")
    action = "removed" if args.remove else "installed"
    print(f"[install] {action} claude-code buddy hooks -> {SETTINGS_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
