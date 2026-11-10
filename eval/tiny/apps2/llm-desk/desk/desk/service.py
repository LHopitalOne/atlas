import logging

from desk.bus import TriagedTicketPublisher
from desk.models import Ticket, TicketStatus
from desk.store import EventBroker, TicketStore
from desk.triage import JevTriager, ReplyDrafter

log = logging.getLogger(__name__)


class Desk:
    """Ties the ticket store to triage, drafting, the stream and live events."""

    def __init__(
        self,
        store: TicketStore,
        events: EventBroker,
        triager: JevTriager,
        drafter: ReplyDrafter,
        publisher: TriagedTicketPublisher,
    ) -> None:
        self.store = store
        self.events = events
        self._triager = triager
        self._drafter = drafter
        self._publisher = publisher

    async def triage(self, ticket_id: str) -> None:
        ticket = self.store.get(ticket_id)
        result = await self._triager.triage(ticket)
        ticket.urgency = result.urgency
        ticket.urgent = result.urgent
        ticket.team = result.team
        ticket.status = TicketStatus.TRIAGED
        entry_id = await self._publisher.publish(ticket)
        log.info("ticket %s triaged team=%s urgent=%s stream_id=%s", ticket.id, ticket.team, ticket.urgent, entry_id)
        self.events.publish("ticket.triaged", ticket.model_dump(mode="json"))

    async def reply(self, ticket: Ticket, agent: str, body: str | None, use_draft: bool) -> Ticket:
        text = await self._drafter.draft(ticket, agent) if use_draft or not body else body
        ticket.replies.append(text)
        ticket.status = TicketStatus.ANSWERED
        self.events.publish("ticket.answered", {"id": ticket.id, "agent": agent, "reply": text})
        return ticket

    def set_status(self, ticket: Ticket, status: TicketStatus) -> Ticket:
        ticket.status = status
        self.events.publish("ticket.status", {"id": ticket.id, "status": status})
        return ticket

    async def aclose(self) -> None:
        await self._triager.aclose()
        await self._drafter.aclose()
        await self._publisher.aclose()
