"""JevRouteJudge: asks Jev on OpenRouter which route receives each request, in parallel, with an answer cache."""

import hashlib
import json
import os
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from ...core.errors import JudgeFailedError, JudgeUnavailableError
from ...usecases.ports import Choice, JudgeCase, RouteJudge
from .question import RouteQuestion


class JevRouteJudge(RouteJudge):
    """One decisions request per case (each has its own state), WORKERS at a time. Answers are cached on disk by the
    exact state and questions, so a second run over unchanged code asks nothing. A case whose request fails is
    answered none (the rules' result stands); when every request fails, the run stops with JudgeFailedError."""

    ENDPOINT = 'https://openrouter.ai/api/alpha/decisions'
    MODEL = 'typesafe/jev-1.14'
    KEY_VARIABLE = 'OPENROUTER_API_KEY'
    WORKERS = 8
    TIMEOUT = 60  # seconds per request
    CACHE = os.path.join(os.path.expanduser('~'), '.cache', 'atlas-bridge', 'jev-answers.json')

    def __init__(self, folders: dict[str, str], cache_path: str | None = None, key: str | None = None):
        self._key = key or os.environ.get(self.KEY_VARIABLE, '')
        if not self._key:
            raise JudgeUnavailableError(self.KEY_VARIABLE)
        self._question = RouteQuestion(folders)
        self._cache_path = cache_path or self.CACHE
        self._cache = self._load()
        self.cost = 0.0  # dollars spent in this run, as OpenRouter reports it
        self.failures: list[str] = []

    def choose(self, cases: list[JudgeCase]) -> list[Choice]:
        bodies = [self._body(case) for case in cases]
        with ThreadPoolExecutor(self.WORKERS) as pool:
            answers = list(pool.map(self._answers, bodies))
        if cases and all(a is None for a in answers):
            raise JudgeFailedError(self.failures[0] if self.failures else 'no answer')
        self._save()
        pairs = zip(cases, answers, strict=True)
        return [self._question.choice(c, a) if a is not None else Choice(None, 0.0) for c, a in pairs]

    def _body(self, case):
        return {'model': self.MODEL, 'state': self._question.state(case), 'questions': self._question.questions(case)}

    def _answers(self, body):
        key = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
        if key in self._cache:
            return self._cache[key]
        try:
            reply = self._post(body)
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            self.failures.append(str(e))
            return None
        self.cost += float((reply.get('usage') or {}).get('cost') or 0.0)
        answers = reply.get('answers')
        if not isinstance(answers, dict):
            self.failures.append(f'no answers in the reply: {str(reply)[:200]}')
            return None
        self._cache[key] = answers
        return answers

    def _post(self, body):
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
            pass  # the cache only saves money; answers this run are already used
