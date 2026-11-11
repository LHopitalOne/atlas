"""MuseDescriber: asks a small chat model on OpenRouter what each file does, in parallel, with an answer cache."""

import os
from concurrent.futures import ThreadPoolExecutor

from ...core.descriptions import Description
from ...core.errors import DescriberFailedError
from ...usecases.ports import FileCase, FileDescriber
from .chat import OpenRouterChat
from .prompt import FilePrompt


class MuseDescriber(FileDescriber):
    """One chat request per file, WORKERS at a time, answering in FilePrompt.SCHEMA with the model's reasoning kept
    minimal (it describes, it does not need to think long; long thinking also eats the answer's token budget).
    Answers are cached by model, path and the exact code read, so unchanged files are never asked about twice."""

    MODEL = OpenRouterChat.MODEL
    WORKERS = 8
    MAX_TOKENS = 1500  # reasoning and answer together
    CACHE = os.path.join(os.path.expanduser('~'), '.cache', 'atlas-bridge', 'file-descriptions.json')

    def __init__(self, folders: dict[str, str], model: str | None = None, cache_path: str | None = None):
        self._chat = OpenRouterChat(cache_path or self.CACHE, model, self.MAX_TOKENS)
        self.model = self._chat.model
        self._prompt = FilePrompt(folders)

    @property
    def cost(self) -> float:
        return self._chat.cost

    @property
    def failures(self) -> list[str]:
        return self._chat.failures

    def describe(self, cases: list[FileCase]) -> list[Description | None]:
        with ThreadPoolExecutor(self.WORKERS) as pool:
            answers = list(pool.map(self._answer, cases))
        if cases and all(a is None for a in answers) and self.failures:
            raise DescriberFailedError(self.failures[0])
        self._chat.save()
        return [FilePrompt.description(a) if a is not None else None for a in answers]

    def _answer(self, case):
        messages = self._prompt.messages(case)
        if messages is None:
            return None
        return self._chat.answer(messages, FilePrompt.SCHEMA, case.path)
