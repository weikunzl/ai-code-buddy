import glob
import queue
import sys
import threading
import time
from typing import Any

from bridge.core.runtime import LineReader
from bridge.core.util import chunk_bytes

NUS_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
NUS_RX_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
NUS_TX_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"


class BLETransport:
    def __init__(self, name_prefix: str = "Claude-") -> None:
        self.name_prefix = name_prefix
        self.loop = None
        self.client = None
        self.write_queue: "queue.Queue[bytes]" = queue.Queue()

    def write(self, data: bytes) -> None:
        self.write_queue.put(data)

    def start(self, reader: LineReader) -> None:
        threading.Thread(target=self._thread_main, args=(reader,), daemon=True).start()

    def _thread_main(self, reader: LineReader) -> None:
        try:
            import asyncio
            from bleak import BleakClient, BleakScanner
        except ImportError:
            print("[ble] install bleak to use --transport ble", file=sys.stderr)
            return

        async def run() -> None:
            while True:
                print(f"[ble] scanning for {self.name_prefix}* ...", file=sys.stderr, flush=True)
                device = await BleakScanner.find_device_by_filter(
                    lambda d, ad: bool(d.name) and d.name.startswith(self.name_prefix),
                    timeout=10.0,
                )
                if not device:
                    print("[ble] no device found, retrying in 3s", file=sys.stderr, flush=True)
                    await asyncio.sleep(3.0)
                    continue
                print(f"[ble] connecting to {device.name} @ {device.address}", file=sys.stderr, flush=True)
                try:
                    async with BleakClient(device) as client:
                        self.client = client
                        print(f"[ble] connected {device.name} @ {device.address}", file=sys.stderr, flush=True)

                        def on_notify(_sender, data: bytearray) -> None:
                            reader.feed(bytes(data))

                        await client.start_notify(NUS_TX_UUID, on_notify)
                        while client.is_connected:
                            try:
                                data = self.write_queue.get_nowait()
                            except queue.Empty:
                                await asyncio.sleep(0.05)
                                continue
                            for chunk in chunk_bytes(data, 180):
                                await client.write_gatt_char(NUS_RX_UUID, chunk, response=False)
                                await asyncio.sleep(0)
                        print(f"[ble] disconnected {device.name}", file=sys.stderr, flush=True)
                except Exception as exc:
                    print(f"[ble] {exc!r}", file=sys.stderr, flush=True)
                    await asyncio.sleep(3.0)
                finally:
                    self.client = None

        asyncio.run(run())
