#!/usr/bin/env python3
"""Prove the Stick reacts to USB serial JSON."""
import argparse
import glob
import json
import sys
import time
import threading

try:
    import serial
except ImportError as exc:
    sys.exit(f"pyserial required: {exc}")


def pick_port(explicit: str | None) -> str:
    if explicit:
        return explicit
    patterns = (
        "/dev/tty.usbmodem*",
        "/dev/cu.usbmodem*",
        "/dev/tty.usbserial-*",
        "/dev/cu.usbserial-*",
    )
    ports = []
    for pattern in patterns:
        ports.extend(sorted(glob.glob(pattern)))
    if not ports:
        sys.exit("no compatible USB serial device found")
    return ports[0]


def count_frames() -> list[dict]:
    return [
        {"total": 0, "running": 0, "waiting": 0, "msg": "usb sleep"},
        {"total": 2, "running": 1, "waiting": 0, "msg": "usb idle"},
        {"total": 4, "running": 3, "waiting": 0, "msg": "usb busy"},
        {"total": 2, "running": 1, "waiting": 1, "msg": "usb wait"},
    ]


def prompt_frames() -> list[dict]:
    return [
        {
            "total": 1,
            "running": 1,
            "waiting": 1,
            "msg": "usb prompt",
            "focused": "usb-session",
            "project": "USB Verify",
            "branch": "feature/connectors",
            "model": "codex",
            "assistant_msg": "Watch for the USB RX prompt",
            "sessions": [
                {
                    "sid": "usb-session",
                    "project": "USB Verify",
                    "branch": "feature/connectors",
                    "phase": "waiting",
                    "model": "codex",
                    "last": "Prompt should appear over USB",
                    "elapsed_s": 42,
                    "pending_s": 9,
                    "focused": True,
                }
            ],
            "pending": [
                {
                    "id": "usb-verify",
                    "sid": "usb-session",
                    "kind": "permission",
                    "title": "USB RX",
                    "body": "serial prompt verify",
                    "pending_s": 9,
                }
            ],
            "prompt": {
                "id": "usb-verify",
                "tool": "USB RX",
                "hint": "serial prompt verify",
            },
        }
    ]


def notice_frames() -> list[dict]:
    return [
        {
            "total": 1,
            "running": 0,
            "waiting": 1,
            "msg": "need host input",
            "focused": "usb-session",
            "project": "USB Verify",
            "branch": "feature/connectors",
            "model": "codex",
            "assistant_msg": "Watch for the notice prompt",
            "sessions": [
                {
                    "sid": "usb-session",
                    "project": "USB Verify",
                    "branch": "feature/connectors",
                    "phase": "waiting",
                    "model": "codex",
                    "last": "Notice should appear over USB",
                    "elapsed_s": 42,
                    "pending_s": 9,
                    "focused": True,
                }
            ],
            "pending": [
                {
                    "id": "notice-verify",
                    "sid": "usb-session",
                    "kind": "notice",
                    "title": "Need host input",
                    "body": "type the answer on your computer",
                    "pending_s": 9,
                    "options": [],
                }
            ],
            "prompt": {
                "id": "notice-verify",
                "tool": "Need host input",
                "hint": "type the answer on your computer",
            },
        }
    ]


def free_text_frames() -> list[dict]:
    return [
        {
            "total": 1,
            "running": 0,
            "waiting": 1,
            "msg": "need details",
            "focused": "usb-session",
            "project": "USB Verify",
            "branch": "feature/connectors",
            "model": "codex",
            "assistant_msg": "Watch for the free-text prompt",
            "sessions": [
                {
                    "sid": "usb-session",
                    "project": "USB Verify",
                    "branch": "feature/connectors",
                    "phase": "waiting",
                    "model": "codex",
                    "last": "Free-text should appear over USB",
                    "elapsed_s": 42,
                    "pending_s": 9,
                    "focused": True,
                }
            ],
            "pending": [
                {
                    "id": "free-text-verify",
                    "sid": "usb-session",
                    "kind": "free_text_required",
                    "title": "Need details",
                    "body": "type the path on your computer",
                    "pending_s": 9,
                    "options": [],
                }
            ],
            "prompt": {
                "id": "free-text-verify",
                "tool": "Need details",
                "hint": "type the path on your computer",
            },
        }
    ]


def free_text_choice_frames() -> list[dict]:
    return [
        {
            "total": 1,
            "running": 0,
            "waiting": 1,
            "msg": "confirm target",
            "focused": "usb-session",
            "project": "USB Verify",
            "branch": "feature/connectors",
            "model": "codex",
            "assistant_msg": "Watch for the quick-reply prompt",
            "sessions": [
                {
                    "sid": "usb-session",
                    "project": "USB Verify",
                    "branch": "feature/connectors",
                    "phase": "waiting",
                    "model": "codex",
                    "last": "Quick replies should appear over USB",
                    "elapsed_s": 42,
                    "pending_s": 9,
                    "focused": True,
                }
            ],
            "pending": [
                {
                    "id": "free-text-choice-verify",
                    "sid": "usb-session",
                    "kind": "free_text_required",
                    "title": "Confirm target",
                    "body": "pick a preset or type on host",
                    "pending_s": 9,
                    "options": [
                        {"id": "here", "label": "Here", "desc": "Use current repo"},
                        {"id": "tmp", "label": "Tmp", "desc": "Use /tmp"},
                    ],
                }
            ],
            "prompt": {
                "id": "free-text-choice-verify",
                "tool": "Confirm target",
                "hint": "pick a preset or type on host",
            },
        }
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", help="serial device path, e.g. /dev/cu.usbmodem144301")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--interval", type=float, default=3.0)
    parser.add_argument("--settle", type=float, default=4.0,
                        help="seconds to wait after opening the port before the first write")
    parser.add_argument("--hold", type=float, default=1.0,
                        help="seconds to keep the port open after the last write")
    parser.add_argument("--profile", choices=("prompt", "counts", "notice", "free_text", "free_text_choice"), default="prompt")
    parser.add_argument("--dtr", action="store_true", help="assert DTR after open")
    parser.add_argument("--rts", action="store_true", help="assert RTS after open")
    parser.add_argument("--readback", action="store_true",
                        help="print newline-delimited device responses while the port is open")
    args = parser.parse_args()

    port = pick_port(args.port)
    if args.profile == "prompt":
        states = prompt_frames()
    elif args.profile == "notice":
        states = notice_frames()
    elif args.profile == "free_text":
        states = free_text_frames()
    elif args.profile == "free_text_choice":
        states = free_text_choice_frames()
    else:
        states = count_frames()

    with serial.Serial(port, args.baud, timeout=1) as s:
        if args.dtr and hasattr(s, "dtr"):
            s.dtr = True
        if args.rts and hasattr(s, "rts"):
            s.rts = True
        stop = threading.Event()
        reader = None
        if args.readback:
            def pump() -> None:
                buf = bytearray()
                while not stop.is_set():
                    chunk = s.read(256)
                    if not chunk:
                        continue
                    for b in chunk:
                        if b in (10, 13):
                            if buf:
                                try:
                                    line = buf.decode("utf-8", errors="replace")
                                finally:
                                    buf.clear()
                                print(f"  <- {line}")
                        else:
                            buf.append(b)

            reader = threading.Thread(target=pump, daemon=True)
            reader.start()
        print(f"opened {port} ({args.profile})")
        if args.settle > 0:
            print(f"waiting {args.settle:.1f}s for device to settle\n")
            time.sleep(args.settle)
        print("writing frames — watch the Stick\n")
        for i in range(args.count):
            st = states[i % len(states)]
            s.write((json.dumps(st) + "\n").encode())
            s.flush()
            print(f"  -> {st}")
            time.sleep(args.interval)
        if args.hold > 0:
            print(f"\nholding port open for {args.hold:.1f}s")
            time.sleep(args.hold)
        stop.set()
        if reader is not None:
            reader.join(timeout=0.5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
