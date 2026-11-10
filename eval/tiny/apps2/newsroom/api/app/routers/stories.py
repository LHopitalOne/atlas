from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.clients import HackerNewsClient
from app.config import settings
from app.deps import get_hn
from app.models import Story

router = APIRouter(prefix="/stories", tags=["stories"])

HN = Annotated[HackerNewsClient, Depends(get_hn)]


@router.get("/top", response_model=list[Story], operation_id="listTopStories")
async def list_top_stories(hn: HN, limit: int | None = None) -> list[Story]:
    print(f"RECV W01 GET /api/v1/stories/top limit={limit}", flush=True)
    return await hn.top_stories(limit or settings.top_limit)


@router.get("/{story_id}", response_model=Story, operation_id="getStory")
async def get_story(story_id: int, hn: HN) -> Story:
    print(f"RECV W02 GET /api/v1/stories/{story_id}", flush=True)
    story = await hn.item(story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="story not found")
    return story
