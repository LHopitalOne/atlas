"""Entities for HTTP links between services: path templates, routes a service serves, requests it sends.

Paths use one canonical syntax whatever the framework: `/rpc/{name}/{version}`, `{*rest}` for a tail wildcard.
Adapters translate Django regexes, Flask converters, axum captures and format strings into it.
"""

import re
from dataclasses import dataclass, field

from .evidence import Assumption

ANY = 'ANY'


@dataclass(frozen=True)
class Segment:
    """One piece of a path between slashes: fixed text, a parameter, or a tail wildcard."""

    LITERAL = 'literal'
    PARAM = 'param'
    REST = 'rest'

    text: str  # the literal text, or the parameter's name
    kind: str = LITERAL

    @property
    def is_literal(self):
        return self.kind == self.LITERAL

    @property
    def is_param(self):
        return self.kind == self.PARAM

    @property
    def is_rest(self):
        return self.kind == self.REST

    def __str__(self):
        if self.is_param and '{' in self.text:  # partly dynamic, like 'v{version}'
            return self.text
        return {self.LITERAL: self.text, self.PARAM: f'{{{self.text}}}', self.REST: f'{{*{self.text}}}'}[self.kind]


@dataclass(frozen=True)
class PathTemplate:
    """A request or route path. Request paths are matched against route paths with fit() and its variants."""

    PLACEHOLDER = re.compile(r'^\{(\*?)([^{}]*)\}$')  # a whole segment '{name}' or '{*name}'
    # How much one aligned pair of segments proves, as (request kind, route kind) -> points. A pair not listed
    # (a literal on a different literal) cannot be served; a request parameter on a route literal proves nothing.
    POINTS = {
        (Segment.LITERAL, Segment.LITERAL): 3,
        (Segment.PARAM, Segment.PARAM): 2,
        (Segment.LITERAL, Segment.PARAM): 1,
        (Segment.PARAM, Segment.LITERAL): 0,
    }

    segments: tuple[Segment, ...]

    @classmethod
    def parse(cls, path: str):
        """'/a/{b}/{*c}' -> segments. Empty segments (double or trailing slashes) are dropped."""
        return cls(tuple(cls._segment(part) for part in path.split('?')[0].split('/') if part))

    @classmethod
    def _segment(cls, part):
        m = cls.PLACEHOLDER.match(part)
        if m:
            return Segment(m.group(2) or 'param', Segment.REST if m.group(1) else Segment.PARAM)
        if '{' in part:  # partly dynamic, like 'v{version}': cannot be compared literally
            return Segment(part, Segment.PARAM)
        return Segment(part.lower())

    def __str__(self):
        return '/' + '/'.join(map(str, self.segments))

    @property
    def size(self):
        """Number of segments. (Not __len__: an empty path '/' must still be truthy.)"""
        return len(self.segments)

    @property
    def literals(self):
        return sum(s.is_literal for s in self.segments)

    def fit(self, route: 'PathTemplate'):
        """How well this request path fits a route path, or None if the route cannot serve it.

        A route's `{*rest}` takes every remaining segment. A route with fixed words must share at least one of
        them with the request: '/api/{id}/envelope' is not a request for '/{org}/issues/{id}'.
        """
        total = self._aligned_points(route)
        if total is None:
            return None
        return total if self._shares_a_word(route) or not route.literals else None

    def stretch_fit(self, route: 'PathTemplate'):
        """Like fit(), but this path's last segment, when it is a parameter, may stand for several route parameters:
        an id like 'partition/key' that holds a slash. None when that does not make it fit."""
        n = self.size
        if not n or not self.segments[-1].is_param or route.size <= n:
            return None
        if not all(r.is_param for r in route.segments[n - 1 :]):
            return None
        head = PathTemplate(self.segments[:-1]).fit(PathTemplate(route.segments[: n - 1]))
        return None if head is None else head + self.POINTS[Segment.PARAM, Segment.PARAM]

    def swallowed_by(self, route: 'PathTemplate'):
        """True when the route's `{*rest}` takes literal segments this path names: a catch-all fallback (often a 404
        handler), not a route made for this request."""
        for i, r in enumerate(route.segments):
            if r.is_rest:
                return any(c.is_literal for c in self.segments[i:])
        return False

    def _aligned_points(self, route):
        total = 0
        for i, r in enumerate(route.segments):
            if r.is_rest or (i < self.size and self.segments[i].is_rest):
                return total
            if i >= self.size:
                return None
            points = self._pair_points(self.segments[i], r)
            if points is None:
                return None
            total += points
        return total if self.size == route.size else None

    def _pair_points(self, mine, route):
        if mine.is_literal and route.is_literal and mine.text != route.text:
            return None
        return self.POINTS[mine.kind, route.kind]

    def _shares_a_word(self, route):
        return any(r.is_literal and i < self.size and self.segments[i].is_literal for i, r in enumerate(route.segments))


@dataclass(frozen=True)
class Route:
    """An HTTP route a repository serves."""

    repo: str
    file: str
    line: int
    path: PathTemplate
    methods: frozenset[str] = frozenset({ANY})
    handler: str = ''
    name: str = ''  # a route name other code can look it up by (Django's `name=`)
    framework: str = ''

    def accepts(self, method: str):
        return method == ANY or ANY in self.methods or method.upper() in self.methods


@dataclass(frozen=True)
class Call:
    """An HTTP request a repository sends, or a URL it hands to another service (kind='payload').

    hints: words near the request that may name the service it goes to (client and variable names, the class,
    the module path, the setting the base URL comes from). A payload call names the route it points at instead
    of a path, and its hints name the service that will fetch the URL.
    """

    REQUEST = 'request'
    PAYLOAD = 'payload'

    repo: str
    file: str
    line: int
    path: PathTemplate | None
    method: str = ANY
    function: str = ''
    hints: frozenset[str] = frozenset()
    kind: str = REQUEST
    route_name: str = ''
    test: bool = False  # only in tests, fixtures or tooling
    assumptions: tuple[Assumption, ...] = ()  # names resolved on the way here; a precise index can check them

    @property
    def is_payload(self):
        return self.kind == self.PAYLOAD


@dataclass
class Extraction:
    """What an extractor found in one repository: the routes it serves and the requests it sends."""

    routes: list[Route] = field(default_factory=list)
    calls: list[Call] = field(default_factory=list)

    def extend(self, other: 'Extraction'):
        self.routes += other.routes
        self.calls += other.calls
        return self
