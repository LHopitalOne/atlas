class QuizBotError(Exception):
    """Base error for the quiz bot."""


class TriviaFetchError(QuizBotError):
    """Open Trivia DB did not return a usable batch of questions."""


class SeedError(QuizBotError):
    """The game-server rejected the seeded questions."""
