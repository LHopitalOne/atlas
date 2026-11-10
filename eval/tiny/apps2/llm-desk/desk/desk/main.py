import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import APIRouter, FastAPI

from desk.api import events, tickets
from desk.bus import TriagedTicketPublisher
from desk.config import get_settings
from desk.service import Desk
from desk.store import EventBroker, TicketStore
from desk.triage import JevTriager, ReplyDrafter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    desk = Desk(
        store=TicketStore(),
        events=EventBroker(),
        triager=JevTriager(settings),
        drafter=ReplyDrafter(settings),
        publisher=TriagedTicketPublisher(settings),
    )
    app.state.desk = desk
    yield
    await desk.aclose()


def create_app() -> FastAPI:
    app = FastAPI(title="llm-desk", lifespan=lifespan)

    api = APIRouter(prefix="/api")
    api.include_router(tickets.router)
    api.include_router(events.router)
    app.include_router(api)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()


def main() -> None:
    settings = get_settings()
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
