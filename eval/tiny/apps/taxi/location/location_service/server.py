import asyncio
import logging

from .dispatch_client import DispatchClient
from .geo import Fix, cell_for
from .settings import settings

log = logging.getLogger(__name__)


class GpsProtocol(asyncio.DatagramProtocol):
    def __init__(self, dispatch: DispatchClient) -> None:
        self.dispatch = dispatch
        self.last_cell: dict[str, str] = {}
        self.tasks: set[asyncio.Task] = set()

    def datagram_received(self, data: bytes, addr) -> None:
        print(f"RECV udp SEND udp:{settings.bind_port}", flush=True)
        try:
            fix = Fix.parse(data)
        except ValueError:
            log.warning("bad datagram from %s: %r", addr, data)
            return

        cell = cell_for(fix.lat, fix.lng, settings.cell_precision)
        if self.last_cell.get(fix.driver_id) == cell:
            return
        self.last_cell[fix.driver_id] = cell

        task = asyncio.create_task(self.dispatch.driver_nearby(fix.driver_id, fix.lat, fix.lng, cell))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)


async def serve() -> None:
    dispatch = DispatchClient(settings.dispatch_url)
    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(
        lambda: GpsProtocol(dispatch),
        local_addr=(settings.bind_host, settings.bind_port),
    )
    log.info("location listening on udp://%s:%s", settings.bind_host, settings.bind_port)
    try:
        await asyncio.Event().wait()
    finally:
        transport.close()
        await dispatch.aclose()
