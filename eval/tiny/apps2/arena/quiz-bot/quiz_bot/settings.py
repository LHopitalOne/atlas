import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    game_server_url: str
    room: str
    bot_name: str
    question_count: int

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            game_server_url=os.environ.get("GAME_SERVER_URL", "http://127.0.0.1:44010"),
            room=os.environ.get("ROOM", "arena-1"),
            bot_name=os.environ.get("BOT_NAME", "trivia-bot"),
            question_count=int(os.environ.get("QUESTION_COUNT", "3")),
        )
