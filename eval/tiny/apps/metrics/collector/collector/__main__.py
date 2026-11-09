import asyncio
import logging
import signal

from aiohttp import web

from .api import create_app
from .settings import load_settings
from .statsd import start_statsd_listener
from .store import MetricStore
from .tcp_ingest import start_tcp_server

log = logging.getLogger("collector")


async def main() -> None:
    settings = load_settings()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    store = MetricStore(retention=settings.retention)

    tcp_server = await start_tcp_server(store, settings)
    udp_transport = await start_statsd_listener(store, settings)

    runner = web.AppRunner(create_app(store), access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, settings.bind_host, settings.http_port)
    await site.start()
    log.info("http api listening on %s:%d", settings.bind_host, settings.http_port)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    await stop.wait()

    log.info("shutting down")
    tcp_server.close()
    await tcp_server.wait_closed()
    udp_transport.close()
    await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
