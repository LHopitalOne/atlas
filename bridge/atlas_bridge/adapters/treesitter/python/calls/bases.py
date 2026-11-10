"""The base URL a request's client was made with (`httpx.AsyncClient(base_url=settings.api_url)`), and URLs the
literal value resolver leaves unknown but configuration gives (`httpx.post(self._url)`, `self._url` from a setting)."""

from typing import NamedTuple

from ..channels.qualified import QualifiedNames
from ..channels.values import ChannelValues
from ..syntax import PythonSyntax
from ..values import Marker, Value


class BaseOption(NamedTuple):
    """A client constructor that takes a base URL every relative request URL is joined to: where it is passed."""

    library: str  # the top-level module
    dotted: str  # the end of the constructor's qualified name
    keyword: str
    position: int | None = None


class ClientBase(NamedTuple):
    """What a client's base URL is: the literal values it may hold, and the expressions it is passed as (named like
    the service, `settings.game_server_url`, when no value is known)."""

    values: tuple = ()
    hints: frozenset = frozenset()


class ClientBases:
    """The base URL of the client a request is sent with, read where the client is made (the receiver's origin:
    `self._http = httpx.AsyncClient(base_url=base_url)`) and settled through constructor arguments, settings
    fields and environment defaults (ChannelValues). httpx and aiohttp join a relative URL to the base's path:
    base 'https://h/v0' and '/item/1.json' send 'https://h/v0/item/1.json'; an absolute URL ignores the base."""

    OPTIONS = (
        BaseOption('httpx', 'Client', 'base_url'),
        BaseOption('httpx', 'AsyncClient', 'base_url'),
        BaseOption('aiohttp', 'ClientSession', 'base_url', 0),
    )
    MAX_BASES = 4
    ABSOLUTE = '://'

    def __init__(self, workspace):
        self._names = QualifiedNames(workspace)
        self.values = ChannelValues(workspace)
        self._seen = {}  # (file, class, function, receiver) -> ClientBase

    def of(self, scope, receiver, made='') -> ClientBase:
        """The base URL of the client `receiver` is (an empty ClientBase when it was made with none). `made`: the
        text of the expression the receiver was made with (SiteHints.origin); one that names no constructor of
        OPTIONS, nor any base keyword, is not followed further."""
        if receiver is None or not any(o.dotted in made or o.keyword in made for o in self.OPTIONS):
            return ClientBase()
        key = (scope.source.path, self._id(scope.cls), self._id(scope.func), PythonSyntax.text(receiver))
        if key not in self._seen:
            self._seen[key] = self._read(scope, receiver)
        return self._seen[key]

    @staticmethod
    def joined(base: str, value: Value) -> Value | None:
        """A relative URL value on the base, or None when the value does not take one (an absolute or unknown URL)."""
        text = value.text
        if value.is_unknown or ClientBases.ABSOLUTE in text or (text.startswith('{') and not Marker.names(text)):
            return None
        return Value(base.rstrip('/') + '/' + text.lstrip('/'), value.hints, value.kind)

    def absolute(self, node, scope) -> list[Value]:
        """The absolute URLs an expression the literal resolver cannot read holds, from configuration."""
        if node is None or node.type not in ('identifier', 'attribute'):
            return []
        found = [v for v in self.values.settled(node, scope) if v.is_literal and self.ABSOLUTE in v.text]
        return found[: self.MAX_BASES]

    def _read(self, scope, receiver):
        values, hints = [], set()
        for origin in self.values.origins.of(receiver, scope):
            given = self._given(origin) if origin.is_call else None
            if given is None:
                continue
            values += [v.text for v in self.values.settled(given, origin.scope) if v.is_literal]
            hints |= self._passed(given, origin.scope)
        return ClientBase(tuple(dict.fromkeys(values))[: self.MAX_BASES], frozenset(hints))

    def _given(self, origin):
        """The base URL argument of a call to a client constructor of OPTIONS, or None."""
        call = origin.node
        qualified = self._names.of(origin.scope.source, call.child_by_field_name('function'))
        for option in self.OPTIONS:
            if QualifiedNames.matches(qualified, option.library, option.dotted):
                pos, kw = PythonSyntax.call_args(call)
                if option.keyword in kw:
                    return kw[option.keyword]
                return pos[option.position] if option.position is not None and option.position < len(pos) else None
        return None

    def _passed(self, node, scope):
        """The expressions callers pass for a base that is a parameter of the function around it."""
        if node.type != 'identifier' or scope.func is None:
            return set()
        name = PythonSyntax.text(node)
        if name not in PythonSyntax.param_names(scope.func):
            return set()
        sites = self.values.origins.sites.of(scope)
        return {Value.hint(PythonSyntax.text(s.bound[name])) for s in sites if name in s.bound}

    @staticmethod
    def _id(node):
        return node.start_byte if node is not None else -1
