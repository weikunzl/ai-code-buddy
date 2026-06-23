#!/usr/bin/env python3
"""POST a test choice prompt to the local bridge (for phone approval smoke tests).

Use _buddy_wait=false so curl returns immediately while the phone shows the modal.

If the phone does not update, ensure only ONE bridge is running: HTTP :9876 and
WS :9877 must be the same process (kill stale python bridge on 9876).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request


def bridge_url() -> str:
    return (
        os.environ.get("BUDDY_BRIDGE_URL")
        or os.environ.get("CURSOR_BUDDY_BRIDGE_URL")
        or "http://127.0.0.1:9876"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Push a test single_choice prompt to bridge HTTP")
    parser.add_argument("--wait", action="store_true", help="block until phone answers (default: no wait)")
    args = parser.parse_args()

    payload = {
        "_buddy_wait": False if not args.wait else True,
        "hook_event_name": "Notification",
        "session_id": "s_demo",
        "cwd": os.getcwd(),
        "message": "Test prompt from push_test_prompt.py",
        "prompt": {
            "id": "q_test",
            "kind": "single_choice",
            "title": "Hello from bridge",
            "body": "Tap an option on your phone",
            "options": [
                {"id": "a", "label": "Approve", "desc": "Looks good"},
                {"id": "b", "label": "Later", "desc": "Not now"},
            ],
        },
    }
    url = bridge_url()
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=35 if args.wait else 5) as resp:
            out = resp.read().decode()
    except TimeoutError:
        print(f"FAIL POST {url}: timed out", file=sys.stderr)
        print(
            "Often two bridge processes: HTTP :9876 and WS :9877 must be ONE process.\n"
            "Fix: ./tools/restart_bridge.sh\n"
            "Then reconnect phone in Settings.",
            file=sys.stderr,
        )
        return 1
    except urllib.error.URLError as exc:
        print(f"FAIL POST {url}: {exc}", file=sys.stderr)
        print("Is bridge running with HTTP on 9876? Same process as WS 9877?", file=sys.stderr)
        return 1
    print(out)
    if not args.wait:
        print("Sent (no wait). Check phone for approval modal.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
