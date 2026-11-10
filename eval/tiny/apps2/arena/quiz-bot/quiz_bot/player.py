import asyncio
import random

import socketio

from quiz_bot.protocol import NAMESPACE, QuizEvent

QuestionPayload = dict[str, str | int | list[str]]
RoundResultPayload = dict[str, str | int | bool | dict[str, int]]


class QuizBotNamespace(socketio.AsyncClientNamespace):
    """Plays the /quiz namespace: joins a room and answers every question it is asked."""

    def __init__(self, room: str, name: str) -> None:
        super().__init__(NAMESPACE)
        self._room = room
        self._name = name
        self.game_over = asyncio.Event()

    async def on_connect(self) -> None:
        await self.emit(QuizEvent.JOIN, {"room": self._room, "name": self._name})

    async def on_question(self, data: QuestionPayload) -> None:
        print(f"RECV A07 quiz-bot question round={data['round']}", flush=True)
        choices = data["choices"]
        guess = random.choice(choices) if isinstance(choices, list) else ""
        await asyncio.sleep(0.1)
        await self.emit(QuizEvent.ANSWER, {"questionId": data["questionId"], "choice": guess})

    async def on_round_result(self, data: RoundResultPayload) -> None:
        print(f"RECV A08 quiz-bot round_result round={data['round']} final={data['final']}", flush=True)
        if data["final"]:
            self.game_over.set()
