#!/usr/bin/env python3
import argparse
import json
import os
import sys
from typing import Any

import hook_relay


def _clip(value: Any, n: int) -> str:
    return str(value or "").replace("\n", " ")[:n]


def build_notification_prompt(obj: dict[str, Any], cwd_default: str | None = None) -> dict[str, Any]:
    if not isinstance(obj, dict):
        raise ValueError("stdin payload must be a JSON object")

    session_id = _clip(obj.get("session_id"), 80)
    if not session_id:
        raise ValueError("session_id is required")

    prompt = obj.get("prompt")
    if not isinstance(prompt, dict):
        raise ValueError("prompt object is required")

    prompt_id = _clip(prompt.get("id"), 40)
    kind = _clip(prompt.get("kind"), 20)
    options = prompt.get("options")
    if not prompt_id:
        raise ValueError("prompt.id is required")
    if kind not in ("single_choice", "multi_choice", "notice", "free_text_required"):
        raise ValueError("prompt.kind must be single_choice, multi_choice, notice, or free_text_required")
    if kind in ("single_choice", "multi_choice") and (not isinstance(options, list) or not options):
        raise ValueError("prompt.options must be a non-empty list")
    if kind in ("notice", "free_text_required") and not isinstance(options, list):
        options = []

    cwd = _clip(obj.get("cwd") or cwd_default or os.getcwd(), 220)
    title = _clip(prompt.get("title"), 40)
    body = _clip(prompt.get("body"), 240)
    message = _clip(obj.get("message") or title or body or kind, 120)

    payload = {
        "hook_event_name": "Notification",
        "session_id": session_id,
        "cwd": cwd,
        "message": message,
        "prompt": {
            "id": prompt_id,
            "kind": kind,
            "title": title or message,
            "body": body or message,
            "options": options,
        },
    }
    model = _clip(obj.get("model"), 24)
    if model:
        payload["model"] = model
    return payload


def forward_notification_prompt(
    raw: bytes,
    *,
    url: str,
    timeout: float,
    strict: bool,
    stdout: Any,
    stderr: Any,
    cwd_default: str | None = None,
    urlopen: Any = None,
) -> int:
    try:
        obj = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"[post-notification-prompt] invalid stdin json: {exc}", file=stderr)
        return 2

    try:
        payload = build_notification_prompt(obj, cwd_default=cwd_default)
    except ValueError as exc:
        print(f"[post-notification-prompt] invalid prompt payload: {exc}", file=stderr)
        return 2

    return hook_relay.forward_hook(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
        url=url,
        timeout=timeout,
        strict=strict,
        stdout=stdout,
        stderr=stderr,
        urlopen=urlopen,
    )


def main(argv: list[str] | None = None, stdin: Any = None, stdout: Any = None, stderr: Any = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bridge-url", default="")
    parser.add_argument("--http-port", type=int, default=9876)
    parser.add_argument("--timeout", type=float, default=35.0)
    parser.add_argument("--fail-open", action="store_true")
    args = parser.parse_args(argv)

    stdin = stdin or sys.stdin.buffer
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    raw = stdin.read()
    return forward_notification_prompt(
        raw,
        url=hook_relay.bridge_url(args),
        timeout=args.timeout,
        strict=not args.fail_open,
        stdout=stdout,
        stderr=stderr,
    )


if __name__ == "__main__":
    raise SystemExit(main())
