from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from desk.models import Ticket
from desk.service import Desk
from desk.store import TicketNotFound


def get_desk(request: Request) -> Desk:
    return request.app.state.desk


DeskDep = Annotated[Desk, Depends(get_desk)]


def load_ticket(ticket_id: str, desk: DeskDep) -> Ticket:
    try:
        return desk.store.get(ticket_id)
    except TicketNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"ticket {ticket_id} not found") from None


TicketDep = Annotated[Ticket, Depends(load_ticket)]
