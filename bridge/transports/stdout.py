import sys


class StdoutTransport:
    def write(self, data: bytes) -> None:
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()
