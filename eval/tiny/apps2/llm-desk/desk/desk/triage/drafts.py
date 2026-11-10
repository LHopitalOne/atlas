from openai import AsyncOpenAI

from desk.config import Settings
from desk.models import Ticket
from desk.observe import recv

SYSTEM_PROMPT = (
    "You are a friendly support agent. Write a short first reply (2-3 sentences) to the customer. "
    "Acknowledge the problem and say which team is looking into it. No placeholders."
)


class ReplyDrafter:
    """Drafts customer replies with a small chat model through OpenRouter's OpenAI-compatible API."""

    def __init__(self, settings: Settings) -> None:
        self._model = settings.draft_model
        self._max_tokens = settings.draft_max_tokens
        self._client = AsyncOpenAI(
            base_url=settings.openrouter_base_url,
            api_key=settings.openrouter_api_key,
            max_retries=1,
            timeout=45.0,
        )

    async def aclose(self) -> None:
        await self._client.close()

    async def draft(self, ticket: Ticket, agent: str) -> str:
        completion = await self._client.chat.completions.create(
            model=self._model,
            max_tokens=self._max_tokens,
            temperature=0.3,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Customer: {ticket.customer}\nTeam: {ticket.team}\nAgent: {agent}\n"
                    f"Subject: {ticket.subject}\n\n{ticket.body}",
                },
            ],
        )
        recv("O2", f"POST openrouter.ai/api/v1/chat/completions ticket={ticket.id} model={completion.model}")
        return (completion.choices[0].message.content or "").strip()
