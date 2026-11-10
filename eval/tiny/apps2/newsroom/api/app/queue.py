"""Hands summarisation jobs to the Rust summarizer over a Redis list."""

import json
import uuid

from redis.asyncio import Redis

from app.models import Story, SummaryJob


class SummaryQueue:
    def __init__(self, redis: Redis, queue_name: str) -> None:
        self._redis = redis
        self._queue = queue_name

    async def enqueue(self, story: Story) -> SummaryJob:
        job = SummaryJob(job_id=uuid.uuid4().hex, story_id=story.id)
        payload = {"job_id": job.job_id, "story_id": story.id, "title": story.title, "kids": story.kids}
        await self._redis.lpush(self._queue, json.dumps(payload))
        return job
