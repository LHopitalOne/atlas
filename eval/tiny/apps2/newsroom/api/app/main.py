import asyncio
import contextlib
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from app.clients import HackerNewsClient
from app.config import API_PREFIX, settings
from app.events import listen_for_done
from app.queue import SummaryQueue
from app.routers import api_router
from app.store import SummaryStore


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    app.state.hn = HackerNewsClient(settings.hn_api_base)
    app.state.queue = SummaryQueue(redis, settings.jobs_queue)
    app.state.store = SummaryStore()
    listener = asyncio.create_task(listen_for_done(redis, settings.done_channel, app.state.store))
    try:
        yield
    finally:
        listener.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await listener
        await app.state.hn.aclose()
        await redis.aclose()


app = FastAPI(title="newsroom api", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(api_router, prefix=API_PREFIX)


@app.get("/healthz", include_in_schema=False)
async def healthz() -> dict[str, str]:
    return {"status": "ok"}
