"""Callbacks from internal workers; not part of the public OpenAPI schema."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.deps import get_store
from app.models import Summary, SummaryResultIn
from app.store import SummaryStore

router = APIRouter(prefix="/internal/summaries", tags=["internal"], include_in_schema=False)


@router.post("/{job_id}/result", response_model=Summary)
async def receive_summary(
    job_id: str,
    result: SummaryResultIn,
    store: Annotated[SummaryStore, Depends(get_store)],
) -> Summary:
    print(f"RECV S01 POST /api/v1/internal/summaries/{job_id}/result story={result.story_id}", flush=True)
    return store.complete(job_id, result)
