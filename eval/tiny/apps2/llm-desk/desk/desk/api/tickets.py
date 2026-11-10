from fastapi import APIRouter, BackgroundTasks, status

from desk.api.deps import DeskDep, TicketDep
from desk.models import ReplyIn, StatusPatch, Ticket, TicketIn
from desk.observe import recv

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=Ticket)
async def create_ticket(data: TicketIn, desk: DeskDep, background: BackgroundTasks) -> Ticket:
    ticket = desk.store.add(data)
    recv("H1", f"POST /api/tickets id={ticket.id} customer={ticket.customer}")
    background.add_task(desk.triage, ticket.id)
    return ticket


@router.get("", response_model=list[Ticket])
async def list_tickets(desk: DeskDep, team: str | None = None, urgent: bool | None = None) -> list[Ticket]:
    tickets = desk.store.query(team=team, urgent=urgent)
    recv("H2", f"GET /api/tickets team={team} urgent={urgent} count={len(tickets)}")
    return tickets


@router.get("/{ticket_id}", response_model=Ticket)
async def get_ticket(ticket: TicketDep) -> Ticket:
    recv("H3", f"GET /api/tickets/{ticket.id}")
    return ticket


@router.post("/{ticket_id}/reply", response_model=Ticket)
async def reply_to_ticket(ticket: TicketDep, data: ReplyIn, desk: DeskDep) -> Ticket:
    recv("H4", f"POST /api/tickets/{ticket.id}/reply agent={data.agent} use_draft={data.use_draft}")
    return await desk.reply(ticket, data.agent, data.body, data.use_draft)


@router.patch("/{ticket_id}", response_model=Ticket)
async def update_ticket(ticket: TicketDep, patch: StatusPatch, desk: DeskDep) -> Ticket:
    recv("H5", f"PATCH /api/tickets/{ticket.id} status={patch.status}")
    return desk.set_status(ticket, patch.status)
