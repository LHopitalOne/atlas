import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from strawberry.fastapi import GraphQLRouter

from .payments import PaymentsClient
from .schema import GraphQLContext, schema
from .settings import get_settings
from .store import BookingStore

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.store = BookingStore.with_sample_rooms()
    app.state.payments = PaymentsClient(
        base_url=settings.payments_url,
        api_key=settings.payments_api_key,
        timeout=settings.payments_timeout,
    )
    yield
    await app.state.payments.aclose()


async def get_context(request: Request) -> GraphQLContext:
    return GraphQLContext(store=request.app.state.store, payments=request.app.state.payments)


app = FastAPI(title="booking-api", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)
app.include_router(GraphQLRouter(schema, context_getter=get_context), prefix="/graphql")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}
