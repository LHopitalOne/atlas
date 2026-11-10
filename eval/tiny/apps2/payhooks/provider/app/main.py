import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import settings
from .events import EventPublisher
from .routes import router
from .settlement import SettlementService
from .webhooks import WebhookDispatcher

logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    publisher = EventPublisher(settings.kafka_brokers)
    webhooks = WebhookDispatcher(settings.webhook_timeout_seconds)
    await publisher.start()
    app.state.settlement = SettlementService(publisher, webhooks, settings.settle_delay_seconds)
    try:
        yield
    finally:
        await webhooks.close()
        await publisher.stop()


app = FastAPI(title="payhooks provider", lifespan=lifespan)
app.include_router(router)
