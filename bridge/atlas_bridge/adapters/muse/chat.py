"""OpenRouterChat: one chat-completions request at a time to a small model on OpenRouter, answering in a JSON schema,
with an answer cache on disk and the cost of what was asked."""

import hashlib
import json
import os
import urllib.error
import urllib.request

from ...core.errors import JudgeUnavailableError


class OpenRouterChat:
    """Answers are cached by model and the exact messages, so a file read once is never asked about twice. A request
    that fails is recorded in `failures` and answered with None. The key is read from the environment, never
    written anywhere."""

    ENDPOINT = 'https://openrouter.ai/api/v1/chat/completions'
    MODEL = 'meta/muse-ember'
    KEY_VARIABLE = 'OPENROUTER_API_KEY'
    TIMEOUT = 120  # seconds per request
    CUT_OFF = 'length'  # the finish reason of an answer that ran out of tokens

    def __init__(self, cache_path: str, model: str | None = None, max_tokens: int = 1500, effort: str = 'minimal'):
        self._key = os.environ.get(self.KEY_VARIABLE, '')
        if not self._key:
            raise JudgeUnavailableError(self.KEY_VARIABLE)
        self.model = model or self.MODEL
        self._max_tokens = max_tokens
        self._effort = effort
        self._cache_path = cache_path
        self._cache = self._load()
        self.cost = 0.0
        self.failures: list[str] = []

    def answer(self, messages: list[dict], schema: dict, label: str = '') -> str | None:
        """The model's answer (JSON text in `schema`), or None when it could not be had. `label` goes into the cache
        key (a file's path)."""
        key = hashlib.sha256(json.dumps([self.model, label, messages], sort_keys=True).encode()).hexdigest()
        if key in self._cache:
            return self._cache[key]
        try:
            reply = self._post(messages, schema)
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            self.failures.append(str(e))
            return None
        self.cost += float((reply.get('usage') or {}).get('cost') or 0.0)
        choice = (reply.get('choices') or [{}])[0]
        content = (choice.get('message') or {}).get('content')
        if choice.get('finish_reason') == self.CUT_OFF:
            self.failures.append(f'the answer about {label or "a file"} ran past {self._max_tokens} tokens')
            return None  # a cut-off answer is not JSON; asking again may fit
        if content:
            self._cache[key] = content
        return content

    def save(self):
        """Write the cache, keeping what another run wrote meanwhile."""
        self._cache = {**self._load(), **self._cache}
        try:
            os.makedirs(os.path.dirname(self._cache_path), exist_ok=True)
            with open(self._cache_path, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f)
        except OSError:
            pass  # the cache only saves money

    def _post(self, messages, schema):
        body = {
            'model': self.model,
            'messages': messages,
            'response_format': {'type': 'json_schema', 'json_schema': schema},
            'max_tokens': self._max_tokens,
            'reasoning': {'effort': self._effort},
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
