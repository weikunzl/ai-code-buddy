#!/usr/bin/env python3
"""Claude Code hook: relay supported events to the buddy bridge."""
from __future__ import annotations

import json
import os
import pathlib
import sys
from typing import Any

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from hooks.common.client import bridge_url
from hooks.common.relay import forward_hook

SUPPORTED = frozenset({
    "SessionStart",
    "UserPromptSubmit",
    "Stop",
    "PreToolUse",
    "Notification",
})


def enrich(payload: dict[str, Any]) -> dict[str, Any]:
    out = dict(payload)
    if not out.get("session_id"):
        out["session_id"] = (
            os.environ.get("CLAUDE_SESSION_ID")
            or os.environ.get("SESSION_ID")
            or ""
        )
    if not out.get("cwd"):
        out["cwd"] = (
            os.environ.get("CLAUDE_CODE_CWD")
            or os.environ.get("PWD")
            or os.getcwd()
        )
    return out


def relay_timeout(event: str) -> float:
    return 30.0 if event == "PreToolUse" else 2.0


def main() -> int:
    raw = sys.stdin.buffer.read()
    if not raw:
        sys.stdout.write("{}\n")
        sys.stdout.flush()
        return 0

    try:
        obj = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return forward_hook(
            raw,
            url=bridge_url(),
            timeout=2.0,
            strict=False,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

    if not isinstance(obj, dict):
        sys.stdout.write("{}\n")
        sys.stdout.flush()
        return 0

    event = str(obj.get("hook_event_name") or "")
    if event not in SUPPORTED:
        sys.stdout.write("{}\n")
        sys.stdout.flush()
        return 0

    body = json.dumps(enrich(obj), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return forward_hook(
        body,
        url=bridge_url(),
        timeout=relay_timeout(event),
        strict=False,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )


if __name__ == "__main__":
    raise SystemExit(main())
