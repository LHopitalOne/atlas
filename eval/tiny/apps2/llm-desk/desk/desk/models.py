from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class TicketStatus(StrEnum):
    NEW = "new"
    TRIAGED = "triaged"
    ANSWERED = "answered"
    CLOSED = "closed"


class TicketIn(BaseModel):
    customer: str
    subject: str
    body: str


class Ticket(TicketIn):
    id: str
    status: TicketStatus = TicketStatus.NEW
    urgent: bool | None = None
    urgency: float | None = None
    team: str | None = None
    replies: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ReplyIn(BaseModel):
    agent: str
    body: str | None = None
    use_draft: bool = False


class StatusPatch(BaseModel):
    status: TicketStatus
