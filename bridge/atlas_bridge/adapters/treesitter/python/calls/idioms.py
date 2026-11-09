"""The ways Python code sends a request: which argument is the URL, which the method, and whether the receiver is
an HTTP client."""

import re
from abc import ABC, abstractmethod
from typing import NamedTuple

from ..syntax import PythonSyntax
from ..verbs import HttpVerbs


class RequestTarget(NamedTuple):
    """What one request call names: its URL argument, its method (a node, or fixed methods) and the receiver kind."""

    url: object
    method_node: object
    methods: list | None
    client: bool


class RequestIdiom(ABC):
    """One request idiom, recognised by the called name."""

    NAMES: frozenset = frozenset()
    CLIENT = re.compile(r'requests|httpx|aiohttp|session|client|http|pool|api|conn', re.I)  # client-like receivers
    NOT_CLIENT = re.compile(r'cache|(^|\.)request\.session$|\.session\[', re.I)  # caches, Django's request.session

    def __init__(self, methods):
        self._methods = methods  # MethodOptions

    @classmethod
    def is_client(cls, receiver):
        """Whether a receiver is named like an HTTP client (and not like a cache or a session store)."""
        t = PythonSyntax.text(receiver)
        return bool(cls.CLIENT.search(t)) and not cls.NOT_CLIENT.search(t)

    @abstractmethod
    def target(self, name, scope, receiver, pos, kw) -> RequestTarget | None:
        """The request a call to `name` sends, or None when it is not one."""


class UrlopenIdiom(RequestIdiom):
    """urllib3 `pool.urlopen(METHOD, url)` and `urllib.request.urlopen(url or Request(url, method=...))`."""

    NAMES = frozenset({'urlopen'})

    def target(self, name, scope, receiver, pos, kw):
        if 'url' in kw:
            url, method_node = kw['url'], kw.get('method', pos[0] if pos else None)
        elif len(pos) >= 2 and self._methods.is_method_arg(scope, pos[0]):
            method_node, url = pos[0], pos[1]
        else:
            url, method_node = (pos[0] if pos else None), kw.get('method')
        if url is not None and url.type == 'call' and PythonSyntax.callee(url) == 'Request':
            rpos, rkw = PythonSyntax.call_args(url)
            method_node = rkw.get('method', method_node)
            url = rkw.get('url', rpos[0] if rpos else None)
        return RequestTarget(url, method_node, None, True)


class RequestMethodIdiom(RequestIdiom):
    """`session.request(method, url)` on any receiver, and generated clients' `client.request(path, method=...)`."""

    NAMES = frozenset({'request'})

    def target(self, name, scope, receiver, pos, kw):
        if receiver is None:
            return None
        if 'method' in kw:  # the method named: the first positional is the URL or path
            url = kw.get('url', kw.get('path', pos[0] if pos else None))
            return RequestTarget(url, kw['method'], None, self.is_client(receiver))
        method_node = pos[0] if pos else None
        url = kw.get('url', pos[1] if len(pos) > 1 else None)
        return RequestTarget(url, method_node, None, self.is_client(receiver))


class VerbIdiom(RequestIdiom):
    """`requests.get(url)`, `client.post(url=...)`: the verb names the method."""

    NAMES = frozenset(HttpVerbs.NAMES)
    SPLATS = frozenset({'list_splat', 'dictionary_splat'})

    def target(self, name, scope, receiver, pos, kw):
        if receiver is None:
            return None
        client = self.is_client(receiver)
        if name == 'get' and not client and self._mapping_get(pos, kw):
            return None
        return RequestTarget(kw.get('url', pos[0] if pos else None), None, [name.upper()], client)

    @classmethod
    def _mapping_get(cls, pos, kw):
        """`mapping.get(key, default)`: two plain positional arguments and no `url=`; `*args, **kwargs` passed on
        are not a key and a default."""
        plain = [a for a in pos if a.type not in cls.SPLATS]
        return 'url' not in kw and len(plain) > 1
