from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse

from desk.api.deps import DeskDep
from desk.observe import recv

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/stream")
async def event_stream(desk: DeskDep, x_agent: str | None = Header(default=None)) -> StreamingResponse:
    recv("S1", f"GET /api/events/stream agent={x_agent}")
    return StreamingResponse(
        desk.events.stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
