import asyncio
import logging

from .server import serve

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

try:
    asyncio.run(serve())
except KeyboardInterrupt:
    pass
