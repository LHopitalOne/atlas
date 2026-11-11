"""MuseReader: asks a small chat model on OpenRouter which requests each file sends, in parallel, with a cache."""

import os
from concurrent.futures import ThreadPoolExecutor

from ...core.errors import ReaderFailedError
from ...usecases.ports import FileReading, ReadCase, RequestReader
from .chat import OpenRouterChat
from .requests import RequestPrompt


class MuseReader(RequestReader):
    """One chat request per file, WORKERS at a time, answering in RequestPrompt.SCHEMA. Reading code for URLs takes
    a little thought, so reasoning is low rather than minimal, with room for it in MAX_TOKENS."""

    MODEL = OpenRouterChat.MODEL
    WORKERS = 8
    MAX_TOKENS = 16000  # reasoning and answer together; a file with many requests and handlers needs a long answer
    EFFORT = 'low'
    CACHE = os.path.join(os.path.expanduser('~'), '.cache', 'atlas-bridge', 'file-requests.json')

    def __init__(self, model: str | None = None, cache_path: str | None = None):
        self._chat = OpenRouterChat(cache_path or self.CACHE, model, self.MAX_TOKENS, self.EFFORT)
        self.model = self._chat.model
        self._prompt = RequestPrompt()

    @property
    def cost(self) -> float:
        return self._chat.cost

    @property
    def failures(self) -> list[str]:
        return self._chat.failures

    def read(self, cases: list[ReadCase]) -> list[FileReading | None]:
        with ThreadPoolExecutor(self.WORKERS) as pool:
            answers = list(pool.map(self._answer, cases))
        if cases and all(a is None for a in answers) and self.failures:
            raise ReaderFailedError(self.failures[0])
        self._chat.save()
        return [RequestPrompt.reading(a) for a in answers]

    def _answer(self, case):
        messages = self._prompt.messages(case)
        return self._chat.answer(messages, RequestPrompt.SCHEMA, f'{case.repo}/{case.path}') if messages else None
