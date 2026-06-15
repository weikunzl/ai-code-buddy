#!/usr/bin/env python3
from __future__ import annotations  # allow `list[str] | None` on Python 3.9 (Apple-shipped)

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any


def bridge_url(args: argparse.Namespace) -> str:
    if args.bridge_url:
        return args.bridge_url
    return f"http://127.0.0.1:{args.http_port}"


def fail_open(stdout: Any) -> int:
    stdout.write("{}\n")
    stdout.flush()
    return 0


def forward_hook(
    raw: bytes,
    *,
    url: str,
    timeout: float,
    strict: bool,
    stdout: Any,
    stderr: Any,
    urlopen: Any = None,
) -> int:
    urlopen = urlopen or urllib.request.urlopen
    try:
        json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        if strict:
            print(f"[hook-relay] invalid stdin json: {exc}", file=stderr)
            return 2
        return fail_open(stdout)

    req = urllib.request.Request(
        url=url,
        data=raw,
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read()
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        if strict:
            print(f"[hook-relay] bridge unavailable: {exc}", file=stderr)
            return 1
        return fail_open(stdout)

    try:
        decoded = body.decode("utf-8")
        json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        if strict:
            print(f"[hook-relay] invalid bridge response: {exc}", file=stderr)
            return 1
        return fail_open(stdout)

    stdout.write(decoded)
    if not decoded.endswith("\n"):
        stdout.write("\n")
    stdout.flush()
    return 0


def main(argv: list[str] | None = None, stdin: Any = None, stdout: Any = None, stderr: Any = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bridge-url", default="")
    parser.add_argument("--http-port", type=int, default=9876)
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    stdin = stdin or sys.stdin.buffer
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    raw = stdin.read()
    return forward_hook(
        raw,
        url=bridge_url(args),
        timeout=args.timeout,
        strict=args.strict,
        stdout=stdout,
        stderr=stderr,
    )


if __name__ == "__main__":
    raise SystemExit(main())
