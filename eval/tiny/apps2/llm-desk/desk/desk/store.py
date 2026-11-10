import asyncio
import itertools
import json
from collections.abc import AsyncIterator

from desk.models import Ticket, TicketIn


class TicketNotFound(LookupError):
    pass


class TicketStore:
    def __init__(self) -> None:
        self._tickets: dict[str, Ticket] = {}
        self._ids = itertools.count(1001)

    def add(self, data: TicketIn) -> Ticket:
        ticket = Ticket(id=f"tkt_{next(self._ids)}", **data.model_dump())
        self._tickets[ticket.id] = ticket
        return ticket

    def get(self, ticket_id: str) -> Ticket:
        try:
            return self._tickets[ticket_id]
        except KeyError:
            raise TicketNotFound(ticket_id) from None

    def query(self, team: str | None = None, urgent: bool | None = None) -> list[Ticket]:
        tickets = self._tickets.values()
        if team is not None:
            tickets = [t for t in tickets if t.team == team]
        if urgent is not None:
            tickets = [t for t in tickets if t.urgent is urgent]
        return sorted(tickets, key=lambda t: (not t.urgent, t.created_at))


class EventBroker:
    """Fan-out of desk events to Server-Sent Events subscribers."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[tuple[str, dict]]] = set()
        self._seq = itertools.count(1)

    def publish(self, event: str, payload: dict) -> None:
        for queue in list(self._subscribers):
            queue.put_nowait((event, payload))

    async def stream(self) -> AsyncIterator[str]:
        queue: asyncio.Queue[tuple[str, dict]] = asyncio.Queue()
        self._subscribers.add(queue)
        try:
            yield ": connected\n\n"
            while True:
                try:
                    event, payload = await asyncio.wait_for(queue.get(), timeout=15)
                except TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                yield f"id: {next(self._seq)}\nevent: {event}\ndata: {json.dumps(payload, default=str)}\n\n"
        finally:
            self._subscribers.discard(queue)
