import asyncio

import httpx
import socketio

from quiz_bot.admin import GameAdminClient
from quiz_bot.player import QuizBotNamespace
from quiz_bot.protocol import NAMESPACE
from quiz_bot.settings import Settings
from quiz_bot.trivia import OpenTriviaClient


class QuizBot:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._admin = GameAdminClient(settings.game_server_url)
        self._sio = socketio.AsyncClient(reconnection=False)
        self._namespace = QuizBotNamespace(settings.room, settings.bot_name)
        self._sio.register_namespace(self._namespace)

    async def seed(self) -> None:
        async with httpx.AsyncClient(timeout=10.0) as http:
            questions = await OpenTriviaClient(http).fetch(self._settings.question_count)
        total = await self._admin.seed_questions(questions)
        print(f"seeded {len(questions)} questions (bank size {total})", flush=True)

    async def play(self) -> None:
        await self._sio.connect(
            self._settings.game_server_url,
            namespaces=[NAMESPACE],
            transports=["websocket"],
            auth={"client": "quiz-bot"},
        )
        await self._namespace.game_over.wait()
        await self._sio.disconnect()

    async def run(self) -> None:
        try:
            await self.seed()
            await self.play()
        finally:
            await self._admin.aclose()


def main() -> None:
    asyncio.run(QuizBot(Settings.from_env()).run())


if __name__ == "__main__":
    main()
