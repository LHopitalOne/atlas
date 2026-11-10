"""Listens for 'summary done' notifications published by the summarizer."""

import asyncio
import json
import logging

from redis.asyncio import Redis

from app.store import SummaryStore

log = logging.getLogger("newsroom.events")


async def listen_for_done(redis: Redis, channel: str, store: SummaryStore) -> None:
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)
    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            event = json.loads(message["data"])
            print(f"RECV R02 SUBSCRIBE {channel} job={event['job_id']} story={event['story_id']}", flush=True)
            store.mark_notified(int(event["story_id"]))
    except asyncio.CancelledError:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
        raise
