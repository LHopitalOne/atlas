"""A request on its way up through wrapper functions: what it holds, what the levels below showed, and the budget of
the whole run."""

from typing import NamedTuple

from .....core.http import PathTemplate
from ..values import Marker, UrlShape


class Reading(NamedTuple):
    """What a request's URL text and method say at one call site."""

    path: str | None
    literals: int  # literal path segments, 0 when the URL does not read as a request path
    pathlike: bool
    open: bool  # parameters (in the URL or the method) wait for a caller
    method_open: bool
    bases: frozenset  # words naming the host

    @classmethod
    def from_request(cls, url_text, method, client):
        url = UrlShape.split(url_text)
        method_open = Marker.is_open(method)
        template = PathTemplate.parse(url.path) if url.path is not None else None
        literals = template.literals if template is not None else 0
        raw = Marker.braces(url_text)
        pathlike = (
            template is not None and UrlShape.pathlike(raw, url.hints, client, literals) and bool(template.segments)
        )
        is_open = bool(Marker.names(url_text)) or method_open
        return cls(url.path, literals if pathlike else 0, pathlike, is_open, method_open, frozenset(url.hints))


class Evidence(NamedTuple):
    """What the levels below already showed: literal path segments, an open method, and base hints."""

    literals: int = 0
    method_open: bool = False
    bases: frozenset = frozenset()

    def then(self, reading: Reading) -> 'Evidence':
        """This evidence with one more level's reading on top."""
        return Evidence(max(reading.literals, self.literals), reading.method_open, self.bases | reading.bases)

    def outdone_by(self, reading: Reading) -> bool:
        """A caller says more than the levels below: more literals, or it settled a method or a base they left
        open."""
        lits = reading.literals
        settled = self.method_open and not reading.method_open or not reading.bases <= self.bases
        return lits > self.literals or (lits >= 1 and settled)


class PendingRequest(NamedTuple):
    """A request still being settled: its URL text and method (either may hold parameter markers), its hints, how
    many wrapper levels it was forwarded through, what those levels showed, and the wrappers on the way (cycles)."""

    url: str
    method: str
    hints: frozenset
    depth: int = 0
    evidence: Evidence = Evidence()
    stack: frozenset = frozenset()
    assumptions: tuple = ()  # Assumptions made on the way: the receiver's origin, each wrapper call followed
    guards: tuple = ()  # Guards: branches on a wrapper's parameters the request is sent in

    def guarded(self, guards) -> 'PendingRequest':
        """The same request, sent only in these branches too."""
        return self._replace(guards=self.guards + guards) if guards else self

    def says_more(self, reading: Reading) -> bool:
        """At the request itself: any literal, or nothing left open. At a caller: more than the levels below."""
        if self.depth == 0:
            return reading.literals >= 1 or not reading.open
        return self.evidence.outdone_by(reading)

    def seen_with(self, reading: Reading) -> 'PendingRequest':
        """The same request, with this level's reading added to its evidence."""
        return self._replace(evidence=self.evidence.then(reading))

    def visit(self, wrapper) -> tuple:
        """The key under which forwarding this request through `wrapper` is done once."""
        return (wrapper, self.url, self.method, self.evidence)

    def forwarded(self, url, method, hints, wrapper, hop=None) -> 'PendingRequest':
        """The request one level up, at a caller of `wrapper` that filled in `url`, `method` and `hints`; `hop` is
        the Assumption that the caller's call reaches the wrapper."""
        assumptions = (*self.assumptions, hop) if hop is not None else self.assumptions
        depth, stack = self.depth + 1, self.stack | {wrapper}
        return PendingRequest(url, method, hints, depth, self.evidence, stack, assumptions, self.guards)


class RequestRun:
    """One request's forwarding: whether its receiver is a client, the visits already made, and the settle budget."""

    MAX_SETTLES = 2000  # call sites one request may be settled at, over all its forwarding chains

    __slots__ = ('_client', '_seen', '_settles')

    def __init__(self, client):
        self._client = client
        self._seen = set()
        self._settles = 0

    @property
    def client(self):
        return self._client

    def spend(self) -> bool:
        """Count one more settle; False once the run is over MAX_SETTLES."""
        self._settles += 1
        return self._settles <= self.MAX_SETTLES

    def first_visit(self, key) -> bool:
        """True the first time a key is visited (and records it), False after."""
        if key in self._seen:
            return False
        self._seen.add(key)
        return True
