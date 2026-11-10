"""Async client for the public Hacker News Firebase API."""

import asyncio

import httpx

from app.models import Story


class HackerNewsClient:
    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self._http = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
            headers={"User-Agent": "newsroom-api/0.1"},
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def top_story_ids(self, limit: int) -> list[int]:
        resp = await self._http.get("/topstories.json")
        resp.raise_for_status()
        print("RECV A01 GET hacker-news.firebaseio.com/v0/topstories.json (caller api)", flush=True)
        return resp.json()[:limit]

    async def item(self, item_id: int) -> Story | None:
        resp = await self._http.get(f"/item/{item_id}.json")
        resp.raise_for_status()
        print(f"RECV A02 GET hacker-news.firebaseio.com/v0/item/{item_id}.json (caller api)", flush=True)
        data = resp.json()
        if not data or data.get("type") != "story":
            return None
        return Story.model_validate(data)

    async def top_stories(self, limit: int) -> list[Story]:
        ids = await self.top_story_ids(limit)
        stories = await asyncio.gather(*(self.item(i) for i in ids))
        return [s for s in stories if s is not None]
