import glob
import queue
import sys
import threading
import time
from typing import Any

from bridge.core.runtime import LineReader


def serial_port_candidates(globber: Any = glob.glob) -> list[str]:
    ports: list[str] = []
    for pattern in (
        "/dev/tty.usbmodem*",
        "/dev/cu.usbmodem*",
        "/dev/tty.usbserial-*",
        "/dev/cu.usbserial-*",
    ):
        ports.extend(sorted(globber(pattern)))
    return ports


def pick_serial_port(explicit: str = "", globber: Any = glob.glob) -> str:
    if explicit:
        return explicit
    ports = serial_port_candidates(globber)
    return ports[0] if ports else ""


class SerialTransport:
    def __init__(self, port: str = "", baud: int = 115200, settle: float = 1.0) -> None:
        self.port = port
        self.baud = baud
        self.settle = settle
        self.write_queue: "queue.Queue[bytes]" = queue.Queue()

    def write(self, data: bytes) -> None:
        self.write_queue.put(data)

    def start(self, reader: LineReader) -> None:
        threading.Thread(target=self._thread_main, args=(reader,), daemon=True).start()

    def _thread_main(self, reader: LineReader) -> None:
        try:
            import serial
        except ImportError:
            print("[serial] install pyserial to use --transport serial", file=sys.stderr)
            return

        while True:
            port = pick_serial_port(self.port)
            if not port:
                print("[serial] no compatible USB serial device found", file=sys.stderr)
                time.sleep(2.0)
                continue
            try:
                with serial.Serial(port, self.baud, timeout=0.1, write_timeout=1) as dev:
                    print(f"[serial] connected {port}", file=sys.stderr)
                    time.sleep(self.settle)
                    while True:
                        try:
                            data = self.write_queue.get(timeout=0.05)
                        except queue.Empty:
                            data = b""
                        if data:
                            dev.write(data)
                            dev.flush()
                        waiting = dev.in_waiting if hasattr(dev, "in_waiting") else 0
                        if waiting:
                            chunk = dev.read(waiting)
                            if chunk:
                                reader.feed(chunk)
            except Exception as exc:
                print(f"[serial] {exc!r}", file=sys.stderr)
                time.sleep(1.0)
