"""MuseDescriber: asks a small chat model on OpenRouter what each file does, in parallel, with an answer cache."""

import hashlib
import json
import os
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from ...core.descriptions import Description
from ...core.errors import DescriberFailedError, JudgeUnavailableError
from ...usecases.ports import FileCase, FileDescriber
from .prompt import FilePrompt


class MuseDescriber(FileDescriber):
    """One chat request per file, WORKERS at a time, answering in FilePrompt.SCHEMA with the model's reasoning kept
    minimal (it describes, it does not need to think long; long thinking also eats the answer's token budget).
    Answers are cached by model, path and the exact code read, so unchanged files are never asked about twice."""

    ENDPOINT = 'https://openrouter.ai/api/v1/chat/completions'
    MODEL = 'meta/muse-ember'
    KEY_VARIABLE = 'OPENROUTER_API_KEY'
    WORKERS = 8
    TIMEOUT = 90  # seconds per request
    MAX_TOKENS = 1500  # reasoning and answer together
    CACHE = os.path.join(os.path.expanduser('~'), '.cache', 'atlas-bridge', 'file-descriptions.json')

    def __init__(self, folders: dict[str, str], model: str | None = None, cache_path: str | None = None):
        self._key = os.environ.get(self.KEY_VARIABLE, '')
        if not self._key:
            raise JudgeUnavailableError(self.KEY_VARIABLE)
        self.model = model or self.MODEL
        self._prompt = FilePrompt(folders)
        self._cache_path = cache_path or self.CACHE
        self._cache = self._load()
        self.cost = 0.0
        self.failures: list[str] = []

    def describe(self, cases: list[FileCase]) -> list[Description | None]:
        with ThreadPoolExecutor(self.WORKERS) as pool:
            answers = list(pool.map(self._answer, cases))
        if cases and all(a is None for a in answers) and self.failures:
            raise DescriberFailedError(self.failures[0])
        self._save()
        return [FilePrompt.description(a) if a is not None else None for a in answers]

    def _answer(self, case):
        messages = self._prompt.messages(case)
        if messages is None:
            return None
        key = hashlib.sha256(json.dumps([self.model, case.path, messages], sort_keys=True).encode()).hexdigest()
        if key in self._cache:
            return self._cache[key]
        try:
            reply = self._post(messages)
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            self.failures.append(str(e))
            return None
        self.cost += float((reply.get('usage') or {}).get('cost') or 0.0)
        content = ((reply.get('choices') or [{}])[0].get('message') or {}).get('content')
        if content:
            self._cache[key] = content
        return content

    def _post(self, messages):
        body = {
            'model': self.model,
            'messages': messages,
            'response_format': {'type': 'json_schema', 'json_schema': FilePrompt.SCHEMA},
            'max_tokens': self.MAX_TOKENS,
            'reasoning': {'effort': 'minimal'},
            'usage': {'include': True},
        }
        request = urllib.request.Request(
            self.ENDPOINT,
            data=json.dumps(body).encode(),
            headers={'Authorization': f'Bearer {self._key}', 'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(request, timeout=self.TIMEOUT) as response:
            return json.loads(response.read().decode())

    def _load(self):
        try:
            with open(self._cache_path, encoding='utf-8') as f:
                found = json.load(f)
        except (OSError, ValueError):
            return {}
        return found if isinstance(found, dict) else {}

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self._cache_path), exist_ok=True)
            with open(self._cache_path, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f)
        except OSError:
            pass  # the cache only saves money
