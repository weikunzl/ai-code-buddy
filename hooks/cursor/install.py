#!/usr/bin/env python3
"""Install (or remove) the Cursor desk-buddy hooks for the current user.

Registers hooks/cursor/hook.py against the relevant Cursor agent events in
~/.cursor/hooks.json so a single hardware buddy reacts to Cursor sessions.
Existing, unrelated hooks are preserved; our entries are matched by their
command path and de-duplicated on every run, so this is safe to re-run.

Usage:
  python3 hooks/cursor/install.py            # install / update
  python3 hooks/cursor/install.py --remove   # uninstall
  python3 hooks/cursor/install.py --print    # show planned hooks.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
HOOK_SCRIPT = REPO_ROOT / "hooks" / "cursor" / "hook.py"
HOOKS_JSON = pathlib.Path.home() / ".cursor" / "hooks.json"

# Events we register, with per-event extras (e.g. a longer timeout for the
# blocking shell-approval hook so the device has time to answer).
EVENTS: dict[str, dict[str, object]] = {
    "sessionStart": {},
    "beforeSubmitPrompt": {},
    "beforeShellExecution": {"timeout": 60},
    "afterShellExecution": {},
    "afterFileEdit": {},
    "stop": {},
}


def hook_command() -> str:
    # Absolute path so it resolves regardless of the hook process cwd.
    return f'/usr/bin/env python3 "{HOOK_SCRIPT}"'


def is_ours(entry: object) -> bool:
    return (
        isinstance(entry, dict)
        and isinstance(entry.get("command"), str)
        and str(HOOK_SCRIPT) in entry["command"]
    )


def load_hooks() -> dict:
    if not HOOKS_JSON.exists():
        return {"version": 1, "hooks": {}}
    try:
        data = json.loads(HOOKS_JSON.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[install] existing hooks.json is unreadable: {exc}", file=sys.stderr)
        sys.exit(1)
    if not isinstance(data, dict):
        data = {}
    data.setdefault("version", 1)
    if not isinstance(data.get("hooks"), dict):
        data["hooks"] = {}
    return data


def strip_ours(data: dict) -> dict:
    hooks = data.get("hooks", {})
    for event in list(hooks.keys()):
        arr = hooks.get(event)
        if isinstance(arr, list):
            kept = [e for e in arr if not is_ours(e)]
            if kept:
                hooks[event] = kept
            else:
                hooks.pop(event, None)
    return data


def add_ours(data: dict) -> dict:
    cmd = hook_command()
    hooks = data["hooks"]
    for event, extras in EVENTS.items():
        entry: dict[str, object] = {"command": cmd}
        entry.update(extras)
        arr = hooks.get(event)
        if not isinstance(arr, list):
            arr = []
        arr.append(entry)
        hooks[event] = arr
    return data


def write_hooks(data: dict) -> None:
    HOOKS_JSON.parent.mkdir(parents=True, exist_ok=True)
    HOOKS_JSON.write_text(json.dumps(data, indent=2) + "\n", "utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--remove", action="store_true", help="uninstall buddy hooks")
    parser.add_argument("--print", dest="dry", action="store_true", help="print result, do not write")
    args = parser.parse_args(argv)

    if not HOOK_SCRIPT.exists():
        print(f"[install] missing {HOOK_SCRIPT}", file=sys.stderr)
        return 1

    data = load_hooks()
    data = strip_ours(data)  # always remove our old entries first (idempotent)
    if not args.remove:
        data = add_ours(data)

    if args.dry:
        print(json.dumps(data, indent=2))
        return 0

    write_hooks(data)
    action = "removed" if args.remove else "installed"
    print(f"[install] {action} cursor-buddy hooks -> {HOOKS_JSON}")
    if not args.remove:
        print(f"[install] hook command: {hook_command()}")
        print("[install] approve mode: risky (set CURSOR_BUDDY_APPROVE=all|off to change)")
        print("[install] reload: Cursor watches hooks.json; if needed, restart Cursor.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
