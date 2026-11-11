"""What the model is shown to find the requests a file sends, the shape its answer must take, and how it is read."""

import json

from ...core.http import Protocol
from ...usecases.ports import FileReading, ReadCase, ReadHelper, ReadRequest, ReadRoute


class RequestPrompt:
    """The file with numbered lines, the helpers of its repository it calls, and a JSON schema for the requests it
    sends and the helpers it defines. The model is told to write only what the code shows; usecases.reading checks
    that it did."""

    MAX_CHARS = 60_000  # a file longer than this is read from its start
    SYSTEM = (
        'You find the network requests in one source file, for a map of how services talk to each other. A request '
        'is code that sends something over the network when it runs: an HTTP call (fetch, axios, requests, httpx, '
        'an HTTP client or SDK method whose URL this file shows), a browser navigation or form to a server URL, a '
        'WebSocket or EventSource, a message published to a queue or topic, a background task enqueued. '
        'For each, give the URL as far as this file shows it. Write a part whose value the file does not show as '
        '{name} (a variable, a parameter, an id), and a base URL that comes from elsewhere as a leading {expression} '
        "('{settings.api_url}/users/{id}'). Join a client's base URL and the path when the file shows both. When a "
        'request sends a variable the file fills above (a list of jobs, a name assigned a constant), report one '
        'request per value it can hold, each on the sending line. Never guess a URL, path or host the file does not '
        'show. Do not report as requests the routes the file serves, nor URLs that are only displayed, compared or '
        'logged, imports, or tests. Also list the helpers the file defines: functions that '
        'send a request whose URL is built from their own parameters, and client objects made with a base URL '
        '(axios.create({baseURL: ...}), httpx.Client(base_url=...)), whose url is that base. Last, list what the file '
        'serves: HTTP routes it declares, and handlers of tasks, jobs, queue or topic messages and events, with the '
        'path or channel as this file declares it. Write a channel named by a constant as the code writes it '
        '(JobName.SendMail), on both sides.'
    )
    REQUEST = {
        'type': 'object',
        'additionalProperties': False,
        'properties': {
            'line': {'type': 'integer', 'description': 'the line number where the request is sent'},
            'code': {'type': 'string', 'description': 'the code on that line, copied exactly'},
            'function': {'type': 'string', 'description': 'the function or method it is in, or ""'},
            'protocol': {'type': 'string', 'enum': sorted(Protocol.ALL)},
            'method': {'type': 'string', 'description': 'GET, POST, PUT, PATCH, DELETE, or "" when not HTTP'},
            'url': {'type': 'string', 'description': "the URL, path or channel name: '{base}/api/items/{id}'"},
            'base': {'type': 'string', 'description': 'the expression the base URL comes from, or ""'},
            'service': {'type': 'string', 'description': 'words in the code naming the service it goes to, or ""'},
            'through': {'type': 'string', 'description': 'the helper listed below it is sent with, or ""'},
        },
        'required': ['line', 'code', 'function', 'protocol', 'method', 'url', 'base', 'service', 'through'],
    }
    HELPER = {
        'type': 'object',
        'additionalProperties': False,
        'properties': {
            'function': {'type': 'string', 'description': 'the name of the function, or of the client object'},
            'kind': {'type': 'string', 'enum': ['function', 'client']},
            'method': {'type': 'string', 'description': "the HTTP method, or '{param}' when a parameter gives it"},
            'url': {
                'type': 'string',
                'description': "the URL with '{param}' for its parameters: '{BASE}/api/{endpoint}'",
            },
        },
        'required': ['function', 'kind', 'method', 'url'],
    }
    ROUTE = {
        'type': 'object',
        'additionalProperties': False,
        'properties': {
            'line': {'type': 'integer', 'description': 'the line where the route or handler is declared'},
            'code': {'type': 'string', 'description': 'the code on that line, copied exactly'},
            'protocol': {'type': 'string', 'enum': sorted(Protocol.ALL)},
            'method': {'type': 'string', 'description': 'GET, POST... or "" for any method or not HTTP'},
            'path': {'type': 'string', 'description': "the route path or channel name: '/api/items/{id}', 'JobName.X'"},
            'function': {'type': 'string', 'description': 'the function that handles it, or ""'},
        },
        'required': ['line', 'code', 'protocol', 'method', 'path', 'function'],
    }
    SCHEMA = {
        'name': 'file_requests',
        'strict': True,
        'schema': {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'requests': {'type': 'array', 'items': REQUEST},
                'helpers': {'type': 'array', 'items': HELPER},
                'serves': {'type': 'array', 'items': ROUTE},
            },
            'required': ['requests', 'helpers', 'serves'],
        },
    }

    @staticmethod
    def _listed(helper):
        if helper.kind == ReadHelper.CLIENT:
            return f'- {helper.function} is a client whose base URL is {helper.url}\n'
        return f'- {helper.function}(...) sends {helper.method} {helper.url}\n'

    def messages(self, case: ReadCase) -> list[dict] | None:
        """The chat messages for one file, or None when it has no code."""
        if not case.text.strip():
            return None
        numbered = '\n'.join(f'{i}| {line}' for i, line in enumerate(case.text[: self.MAX_CHARS].splitlines(), 1))
        helpers = ''.join(map(self._listed, case.helpers))
        listed = f'Helpers defined elsewhere in this repository that this file calls:\n{helpers}\n' if helpers else ''
        return [
            {'role': 'system', 'content': self.SYSTEM},
            {'role': 'user', 'content': f'Repository: {case.repo}\nFile: {case.path}\n\n{listed}```\n{numbered}\n```'},
        ]

    @classmethod
    def reading(cls, content: str | None) -> FileReading | None:
        """The model's JSON answer as a FileReading, or None when it is not one."""
        try:
            found = json.loads(content or '')
        except ValueError:
            return None
        if not isinstance(found, dict):
            return None
        requests = tuple(r for r in map(cls._request, cls._items(found, 'requests')) if r is not None)
        helpers = tuple(h for h in map(cls._helper, cls._items(found, 'helpers')) if h is not None)
        routes = tuple(r for r in map(cls._route, cls._items(found, 'serves')) if r is not None)
        return FileReading(requests, helpers, routes)

    @staticmethod
    def _items(found, key):
        items = found.get(key)
        return [i for i in items if isinstance(i, dict)] if isinstance(items, list) else []

    @staticmethod
    def _request(item):
        try:
            line = int(item.get('line') or 0)
        except (TypeError, ValueError):
            return None
        text = {
            k: str(item.get(k) or '')
            for k in ('code', 'method', 'url', 'protocol', 'function', 'base', 'service', 'through')
        }
        return ReadRequest(line, **text) if text['url'] and text['code'] else None

    @staticmethod
    def _route(item):
        try:
            line = int(item.get('line') or 0)
        except (TypeError, ValueError):
            return None
        text = {k: str(item.get(k) or '') for k in ('code', 'method', 'path', 'protocol', 'function')}
        return ReadRoute(line, **text) if text['path'] and text['code'] else None

    @staticmethod
    def _helper(item):
        function, url = str(item.get('function') or ''), str(item.get('url') or '')
        kind = ReadHelper.CLIENT if item.get('kind') == ReadHelper.CLIENT else ReadHelper.FUNCTION
        return ReadHelper(function, str(item.get('method') or ''), url, kind) if function and url else None
