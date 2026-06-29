#!/usr/bin/env python3
"""Install (or remove) the TRAE desk-buddy hooks.

Registers hooks/trae/hook.py in TRAE's nested hooks.json format (see
https://docs.trae.cn/ide_hook-configuration-reference). Existing unrelated
hooks are preserved; our entries are matched by command path and de-duplicated
on every run.

By default installs to the global config (~/.trae-cn/hooks.json) so every
TRAE workspace gets the buddy. Use --project to install under .trae/hooks.json
in a specific repo instead.

Usage:
  python3 hooks/trae/install.py                       # global install
  python3 hooks/trae/install.py --project             # install to $PWD/.trae
  python3 hooks/trae/install.py --project-dir /repo   # install to specific project
  python3 hooks/trae/install.py --remove              # uninstall
  python3 hooks/trae/install.py --print               # show planned hooks.json
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
HOOK_SCRIPT = REPO_ROOT / "hooks" / "trae" / "hook.py"

# TRAE documented events. One nested hook group per event; PreToolUse gets a
# longer timeout because it may wait for a hardware approval.
EVENTS: dict[str, dict[str, object]] = {
    "SessionStart": {},
    "UserPromptSubmit": {},
    "PreToolUse": {"timeout": 60},
    "PostToolUse": {"matcher": "*"},
    "Stop": {},
}


def global_hooks_path() -> pathlib.Path:
    return pathlib.Path.home() / ".trae-cn" / "hooks.json"


def project_hooks_path(project_dir: pathlib.Path) -> pathlib.Path:
    return project_dir / ".trae" / "hooks.json"


def hook_command() -> str:
    return f'/usr/bin/env PYTHONPATH="{REPO_ROOT}" python3 "{HOOK_SCRIPT}"'


def command_in_entry(entry: object) -> str | None:
    if not isinstance(entry, dict):
        return None
    cmd = entry.get("command")
    return cmd if isinstance(cmd, str) else None


def is_ours_entry(entry: object) -> bool:
    cmd = command_in_entry(entry)
    return bool(cmd and str(HOOK_SCRIPT) in cmd)


def is_ours_group(group: object) -> bool:
    if not isinstance(group, dict):
        return False
    inner = group.get("hooks")
    if isinstance(inner, list):
        return any(is_ours_entry(item) for item in inner)
    return is_ours_entry(group)


def load_hooks(path: pathlib.Path) -> dict:
    if not path.exists():
        return {"version": 1, "hooks": {}}
    try:
        data = json.loads(path.read_text("utf-8"))
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
        if not isinstance(arr, list):
            continue
        kept = [g for g in arr if not is_ours_group(g)]
        if kept:
            hooks[event] = kept
        else:
            hooks.pop(event, None)
    return data


def make_group(extras: dict[str, object]) -> dict[str, object]:
    inner: dict[str, object] = {
        "type": "command",
        "command": hook_command(),
        "timeout": extras.get("timeout", 30),
    }
    group: dict[str, object] = {"hooks": [inner]}
    if "matcher" in extras:
        group["matcher"] = extras["matcher"]
    return group


def add_ours(data: dict) -> dict:
    hooks = data["hooks"]
    for event, extras in EVENTS.items():
        group = make_group(extras)
        arr = hooks.get(event)
        if not isinstance(arr, list):
            arr = []
        arr.append(group)
        hooks[event] = arr
    return data


def write_hooks(data: dict, path: pathlib.Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", "utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project",
        action="store_true",
        help="install to project .trae/hooks.json instead of global ~/.trae-cn",
    )
    parser.add_argument(
        "--project-dir",
        default=os.getcwd(),
        help="project directory when using --project (default: $PWD)",
    )
    parser.add_argument("--remove", action="store_true", help="uninstall buddy hooks")
    parser.add_argument("--print", dest="dry", action="store_true", help="print result, do not write")
    args = parser.parse_args(argv)

    if not HOOK_SCRIPT.exists():
        print(f"[install] missing {HOOK_SCRIPT}", file=sys.stderr)
        return 1

    if args.project:
        path = project_hooks_path(pathlib.Path(args.project_dir).resolve())
        scope = f"project {path}"
    else:
        path = global_hooks_path()
        scope = f"global {path}"

    data = load_hooks(path)
    data = strip_ours(data)
    if not args.remove:
        data = add_ours(data)

    if args.dry:
        print(json.dumps(data, indent=2))
        return 0

    write_hooks(data, path)
    action = "removed" if args.remove else "installed"
    print(f"[install] {action} trae-buddy hooks -> {path} ({scope})")
    if not args.remove:
        print(f"[install] hook command: {hook_command()}")
        print("[install] approve mode: risky (set TRAE_BUDDY_APPROVE=all|off to change)")
        print("[install] restart TRAE or reload the workspace for hooks to take effect.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
