#!/usr/bin/env python3
import json

import session_bridge


def main() -> int:
    for profile in ("permission", "single", "multi"):
        for frame in session_bridge.simulator_frames(now=1777180820, profile=profile):
            line = session_bridge.encode_line(frame).decode("utf-8").strip()
            obj = json.loads(line)
            print(line)
            assert "total" in obj
            assert "running" in obj
            assert "waiting" in obj
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
