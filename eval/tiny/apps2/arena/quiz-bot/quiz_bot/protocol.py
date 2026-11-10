from enum import StrEnum

# Mirror of game-server/src/events.ts
NAMESPACE = "/quiz"


class QuizEvent(StrEnum):
    JOIN = "join"
    ANSWER = "answer"
    QUESTION = "question"
    ROUND_RESULT = "round_result"
