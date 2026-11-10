import httpx

from quiz_bot.errors import SeedError
from quiz_bot.trivia import TriviaQuestion


class GameAdminClient:
    """Client for the game-server's admin REST API."""

    def __init__(self, base_url: str) -> None:
        self._http = httpx.AsyncClient(base_url=base_url, timeout=5.0)

    async def seed_questions(self, questions: list[TriviaQuestion]) -> int:
        payload = {"questions": [q.to_json() for q in questions]}
        response = await self._http.post("/admin/questions", json=payload)
        if response.status_code != httpx.codes.CREATED:
            raise SeedError(f"seeding failed with {response.status_code}: {response.text}")
        return int(response.json()["total"])

    async def aclose(self) -> None:
        await self._http.aclose()
