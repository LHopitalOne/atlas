from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.clients import HackerNewsClient
from app.deps import get_hn, get_queue, get_store
from app.models import Summary, SummaryJob, SummaryRequest
from app.queue import SummaryQueue
from app.store import SummaryStore

router = APIRouter(prefix="/summaries", tags=["summaries"])


@router.post(
    "",
    response_model=SummaryJob,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="requestSummary",
)
async def request_summary(
    body: SummaryRequest,
    hn: Annotated[HackerNewsClient, Depends(get_hn)],
    queue: Annotated[SummaryQueue, Depends(get_queue)],
    store: Annotated[SummaryStore, Depends(get_store)],
) -> SummaryJob:
    print(f"RECV W03 POST /api/v1/summaries story={body.story_id}", flush=True)
    story = await hn.item(body.story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="story not found")
    job = await queue.enqueue(story)
    store.mark_queued(job.job_id, story.id)
    return job


@router.get("/{story_id}", response_model=Summary, operation_id="getSummary")
async def get_summary(story_id: int, store: Annotated[SummaryStore, Depends(get_store)]) -> Summary:
    print(f"RECV W04 GET /api/v1/summaries/{story_id}", flush=True)
    summary = store.get(story_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="no summary requested for this story")
    return summary
