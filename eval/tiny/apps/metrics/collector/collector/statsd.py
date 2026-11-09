import asyncio
import logging
import time

from .settings import Settings
from .store import MetricStore, Sample

log = logging.getLogger(__name__)


class StatsdProtocol(asyncio.DatagramProtocol):
    def __init__(self, store: MetricStore, port: int) -> None:
        self.store = store
        self.port = port

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        log.info("RECV udp SEND udp:%d", self.port)
        for packet in data.decode(errors="replace").splitlines():
            self._handle(packet.strip(), addr)

    def _handle(self, packet: str, addr: tuple[str, int]) -> None:
        try:
            name, rest = packet.split(":", 1)
            raw_value, kind = rest.split("|")[:2]
            value = float(raw_value)
        except ValueError:
            log.warning("bad statsd packet from %s: %r", addr, packet)
            return

        if kind == "c":
            self.store.incr(name, value)
        elif kind in ("g", "ms"):
            self.store.add(Sample(name=name, value=value, timestamp=time.time()))
        else:
            log.warning("unsupported statsd type %r", kind)


async def start_statsd_listener(store: MetricStore, settings: Settings) -> asyncio.DatagramTransport:
    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(
        lambda: StatsdProtocol(store, settings.statsd_port),
        local_addr=(settings.bind_host, settings.statsd_port),
    )
    log.info("statsd listening on %s:%d/udp", settings.bind_host, settings.statsd_port)
    return transport
