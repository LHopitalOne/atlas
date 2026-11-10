import asyncio
import html
from dataclasses import asdict, dataclass

import httpx

from quiz_bot.errors import TriviaFetchError

OPENTDB_URL = "https://opentdb.com/api.php"
RATE_LIMITED = 5


@dataclass(frozen=True, slots=True)
class TriviaQuestion:
    category: str
    question: str
    correct_answer: str
    incorrect_answers: list[str]

    @classmethod
    def from_api(cls, raw: dict[str, str | list[str]]) -> "TriviaQuestion":
        incorrect = raw["incorrect_answers"]
        return cls(
            category=html.unescape(str(raw["category"])),
            question=html.unescape(str(raw["question"])),
            correct_answer=html.unescape(str(raw["correct_answer"])),
            incorrect_answers=[html.unescape(a) for a in incorrect] if isinstance(incorrect, list) else [],
        )

    def to_json(self) -> dict[str, str | list[str]]:
        return asdict(self)


class OpenTriviaClient:
    """Fetches multiple-choice questions from the public Open Trivia DB."""

    def __init__(self, http: httpx.AsyncClient, attempts: int = 4) -> None:
        self._http = http
        self._attempts = attempts

    async def fetch(self, amount: int) -> list[TriviaQuestion]:
        for _ in range(self._attempts):
            response = await self._http.get(OPENTDB_URL, params={"amount": amount, "type": "multiple"})
            response.raise_for_status()
            body = response.json()
            if body.get("response_code") == RATE_LIMITED:
                await asyncio.sleep(5.5)
                continue
            if body.get("response_code") != 0:
                raise TriviaFetchError(f"opentdb response_code={body.get('response_code')}")
            print(f"RECV O01 quiz-bot GET opentdb.com/api.php amount={amount}", flush=True)
            return [TriviaQuestion.from_api(item) for item in body["results"]]
        raise TriviaFetchError("opentdb kept rate limiting us")
