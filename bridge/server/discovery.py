import socket

from zeroconf import ServiceInfo, Zeroconf

SERVICE_TYPE = "_buddy._tcp.local."


def _local_address() -> bytes:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return socket.inet_aton(sock.getsockname()[0])
    except OSError:
        return socket.inet_aton("127.0.0.1")
    finally:
        sock.close()


class BuddyDiscovery:
    def __init__(self, ws_port: int, http_port: int, name: str | None = None) -> None:
        self.ws_port = ws_port
        self.http_port = http_port
        self.name = name or socket.gethostname()
        self._zc: Zeroconf | None = None
        self._info: ServiceInfo | None = None

    def register(self) -> None:
        self._zc = Zeroconf()
        self._info = ServiceInfo(
            SERVICE_TYPE,
            f"{self.name}.{SERVICE_TYPE}",
            addresses=[_local_address()],
            port=self.ws_port,
            properties={
                "version": "1",
                "http": str(self.http_port),
                "name": self.name,
            },
        )
        self._zc.register_service(self._info)

    def unregister(self) -> None:
        if self._zc is not None and self._info is not None:
            self._zc.unregister_service(self._info)
            self._zc.close()
        self._zc = None
        self._info = None
