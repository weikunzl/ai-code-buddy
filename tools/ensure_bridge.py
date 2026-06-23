#!/usr/bin/env python3
"""Start the local bridge if HTTP/WS ports are not already listening."""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hooks.common.ensure_bridge import (  # noqa: E402
    bridge_http_url,
    bridge_is_running,
    ensure_bridge_running,
)


def main() -> int:
    url = bridge_http_url()
    if bridge_is_running(url):
        print(f"[ensure] bridge already running ({url})")
        return 0
    ok = ensure_bridge_running(url)
    if ok:
        print(f"[ensure] bridge started ({url})")
        return 0
    print(f"[ensure] bridge not reachable ({url})", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
