from dataclasses import dataclass

import httpx

from desk.config import Settings
from desk.models import Ticket
from desk.observe import recv

DECISIONS_PATH = "/api/alpha/decisions"


@dataclass(frozen=True, slots=True)
class TriageResult:
    urgency: float
    team: str
    team_scores: dict[str, float]

    @property
    def urgent(self) -> bool:
        return self.urgency >= 0.5


class JevTriager:
    """Asks Jev (TypeSafe System One, served by OpenRouter) for typed triage judgments."""

    def __init__(self, settings: Settings) -> None:
        self._model = settings.jev_model
        self._teams = settings.teams
        self._http = httpx.AsyncClient(
            base_url=settings.openrouter_url,
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "X-Title": "llm-desk",
            },
            timeout=httpx.Timeout(45.0, connect=10.0),
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    def _questions(self) -> dict[str, dict[str, str]]:
        questions = {
            "urgent": {
                "type": "noul",
                "instructions": "Is this support ticket urgent: an outage, data loss, a security problem "
                "or a customer fully blocked from working?",
            }
        }
        for team in self._teams:
            questions[f"team_{team}"] = {
                "type": "noul",
                "instructions": f"Should the '{team}' support team own this ticket?",
            }
        return questions

    async def triage(self, ticket: Ticket) -> TriageResult:
        payload = {
            "model": self._model,
            "state": {"customer": ticket.customer, "subject": ticket.subject, "body": ticket.body},
            "questions": self._questions(),
        }
        response = await self._http.post(DECISIONS_PATH, json=payload)
        response.raise_for_status()
        answers = response.json()["answers"]
        recv("O1", f"POST openrouter.ai{DECISIONS_PATH} ticket={ticket.id} status={response.status_code}")

        scores = {team: float(answers[f"team_{team}"]["noul"]) for team in self._teams}
        return TriageResult(
            urgency=float(answers["urgent"]["noul"]),
            team=max(scores, key=scores.__getitem__),
            team_scores=scores,
        )
