from redis.asyncio import Redis

from desk.config import Settings
from desk.models import Ticket


class TriagedTicketPublisher:
    """Appends triaged tickets to a Redis stream for downstream consumers."""

    def __init__(self, settings: Settings) -> None:
        self._redis = Redis.from_url(settings.redis_url, decode_responses=True)
        self._stream = settings.triaged_stream

    async def aclose(self) -> None:
        await self._redis.aclose()

    async def publish(self, ticket: Ticket) -> str:
        fields = {
            "ticket_id": ticket.id,
            "team": ticket.team or "unassigned",
            "urgent": "1" if ticket.urgent else "0",
            "urgency": f"{ticket.urgency or 0.0:.3f}",
            "created_at": ticket.created_at.isoformat(),
        }
        return await self._redis.xadd(self._stream, fields, maxlen=10_000, approximate=True)
