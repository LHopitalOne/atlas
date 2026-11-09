import asyncio
import logging
import time

from .settings import Settings
from .store import MetricStore, Sample

log = logging.getLogger(__name__)


class ParseError(ValueError):
    pass


def parse_line(line: str) -> Sample:
    """Parse `<name> <value> [timestamp] [key=value ...]`."""
    parts = line.split()
    if len(parts) < 2:
        raise ParseError(f"expected at least name and value: {line!r}")
    name, raw_value, *rest = parts
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ParseError(f"bad value {raw_value!r}") from exc

    timestamp = time.time()
    tags: dict[str, str] = {}
    for token in rest:
        if "=" in token:
            key, _, val = token.partition("=")
            tags[key] = val
        else:
            timestamp = float(token)
    return Sample(name=name, value=value, timestamp=timestamp, tags=tags)


class LineProtocolHandler:
    def __init__(self, store: MetricStore, port: int) -> None:
        self.store = store
        self.port = port

    async def __call__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        log.debug("connection from %s", peer)
        try:
            while raw := await reader.readline():
                line = raw.decode().strip()
                if not line:
                    continue
                log.info("RECV tcp SEND tcp:%d", self.port)
                try:
                    self.store.add(parse_line(line))
                except ParseError as exc:
                    log.warning("dropping line from %s: %s", peer, exc)
        finally:
            writer.close()
            await writer.wait_closed()


async def start_tcp_server(store: MetricStore, settings: Settings) -> asyncio.Server:
    handler = LineProtocolHandler(store, settings.tcp_port)
    server = await asyncio.start_server(handler, settings.bind_host, settings.tcp_port)
    log.info("line protocol listening on %s:%d", settings.bind_host, settings.tcp_port)
    return server
