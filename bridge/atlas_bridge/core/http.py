"""Entities for links between services: path templates, routes a service serves, requests it sends.

Paths use one canonical syntax whatever the framework: `/rpc/{name}/{version}`, `{*rest}` for a tail wildcard.
Adapters translate Django regexes, Flask converters, axum captures and format strings into it. A link over another
protocol uses the same model: its channel is the path (a topic or queue `/orders.created`, a gRPC method
`/Service/Method`, a port `/41210`, a background task `/app.tasks.send_mail`), and a route and a call only meet on the
same protocol.
"""

import re
from dataclasses import dataclass, field

from .evidence import Assumption

ANY = 'ANY'


class Protocol:
    """What a route or call travels over. HTTP is the default; the others name their channel as a one- or two-segment
    path (see the module docstring)."""

    HTTP = 'http'
    WEBSOCKET = 'websocket'
    GRPC = 'grpc'
    GRAPHQL = 'graphql'
    KAFKA = 'kafka'
    AMQP = 'amqp'
    REDIS = 'redis'
    TCP = 'tcp'
    UDP = 'udp'
    TASK = 'task'  # a background job handed to workers through a task library (Celery, BullMQ, RQ): its channel is the
    # task's name (Celery: the task function's dotted path or its name=; BullMQ: '<queue>/<job name>')
    ALL = frozenset({HTTP, WEBSOCKET, GRPC, GRAPHQL, KAFKA, AMQP, REDIS, TCP, UDP, TASK})


@dataclass(frozen=True)
class Segment:
    """One piece of a path between slashes: fixed text, a parameter, or a tail wildcard."""

    LITERAL = 'literal'
    PARAM = 'param'
    REST = 'rest'
    PLACEHOLDERS = re.compile(r'\{[^{}]*\}')  # the dynamic parts of a partly dynamic segment

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

    @property
    def skeleton(self):
        """The fixed text of a segment with its dynamic parts blanked: 'swagger.{format}' -> 'swagger.{}'."""
        return self.PLACEHOLDERS.sub('{}', self.text) if self.is_param and '{' in self.text else self.text

    def admits(self, text):
        """Whether literal text fits this partly literal segment: its fixed pieces, in order ('swagger.json' fits
        'swagger.{format}', 'accounts' does not)."""
        pieces = self.skeleton.split('{}')
        if not text.startswith(pieces[0]) or not text.endswith(pieces[-1]):
            return False
        at = len(pieces[0])
        for piece in pieces[1:-1]:
            at = text.find(piece, at)
            if at < 0:
                return False
            at += len(piece)
        return at <= len(text) - len(pieces[-1])

    @property
    def is_partly_literal(self):
        """A parameter with fixed text around it: 'v{version}', 'swagger.{format}'."""
        return self.is_param and '{' in self.text and bool(self.PLACEHOLDERS.sub('', self.text))

    def __str__(self):
        if self.is_param and '{' in self.text:  # partly dynamic, like 'v{version}'
            return self.text
        return {self.LITERAL: self.text, self.PARAM: f'{{{self.text}}}', self.REST: f'{{*{self.text}}}'}[self.kind]


@dataclass(frozen=True)
class PathTemplate:
    """A request or route path. Request paths are matched against route paths with fit() and its variants."""

    PLACEHOLDER = re.compile(r'^\{(\*?)([^{}]*)\}$')  # a whole segment '{name}' or '{*name}'
    VERSION = re.compile(r'^v\d+$')  # an API version segment: 'v1', 'v2'
    API = 'api'
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

    @property
    def fixed(self):
        """Segments with fixed text: literals and partly literal ones ('swagger.{format}')."""
        return sum(s.is_literal or s.is_partly_literal for s in self.segments)

    @property
    def has_rest(self):
        return any(s.is_rest for s in self.segments)

    @property
    def is_api(self):
        """A path under an API prefix: an 'api' segment or a version ('/api/0', '/v2/grades')."""
        return any(s.is_literal and (s.text == self.API or self.VERSION.match(s.text)) for s in self.segments)

    def fit(self, route: 'PathTemplate'):
        """How well this request path fits a route path, or None if the route cannot serve it.

        A route's `{*rest}` takes every remaining segment. A route with fixed words must share at least one of
        them with the request: '/api/{id}/envelope' is not a request for '/{org}/issues/{id}'. A route of parameters
        only ('/{slug}') does not take a request with fixed words ('/accounts'): that would be a fallback, not a match.
        """
        if self.literals and not route.fixed and not route.has_rest:
            return None
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

    def prefixed_fit(self, route: 'PathTemplate', max_prefix: int):
        """(points, prefix) when the route is this path behind 1 to `max_prefix` fixed segments ('/api/v1' +
        '/courses'): the part a base URL like 'http://catalog/api/v1' carries. None when it is not."""
        extra = route.size - self.size
        if not self.literals or not 1 <= extra <= max_prefix:
            return None
        head, tail = PathTemplate(route.segments[:extra]), PathTemplate(route.segments[extra:])
        if head.literals != extra or not head.is_api or not self._shares_a_word(tail) or self.swallowed_by(tail):
            return None
        points = self.fit(tail)
        return None if points is None else (points, head)

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
        if route.is_partly_literal and not (
            mine.skeleton == route.skeleton or mine.is_literal and route.admits(mine.text)
        ):
            return None  # '{name}' or 'accounts' is not 'swagger.{format}'; 'swagger.json' and '{a},{b}' fit
        return self.POINTS[mine.kind, route.kind]

    def _shares_a_word(self, route):
        return any(r.is_literal and i < self.size and self.segments[i].is_literal for i, r in enumerate(route.segments))


@dataclass(frozen=True)
class Route:
    """A route a repository serves: an HTTP route, or a channel it receives on (protocol)."""

    repo: str
    file: str
    line: int
    path: PathTemplate
    methods: frozenset[str] = frozenset({ANY})
    handler: str = ''
    name: str = ''  # a route name other code can look it up by (Django's `name=`)
    framework: str = ''
    protocol: str = Protocol.HTTP

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
    ORIGIN = '//'  # marks the hint that is the host of an absolute URL the code writes: '//api.linkedin.com'

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
    protocol: str = Protocol.HTTP

    @property
    def is_payload(self):
        return self.kind == self.PAYLOAD

    @property
    def host(self) -> str:
        """The host of the absolute URL the request is sent to, when the code writes one ('api.linkedin.com')."""
        return next((h[len(self.ORIGIN) :] for h in sorted(self.hints) if h.startswith(self.ORIGIN)), '')


@dataclass
class Extraction:
    """What an extractor found in one repository: the routes it serves, the requests it sends, and the service URLs
    its configuration names (core.addresses.ServiceUrl)."""

    routes: list[Route] = field(default_factory=list)
    calls: list[Call] = field(default_factory=list)
    urls: list = field(default_factory=list)

    def extend(self, other: 'Extraction'):
        self.routes += other.routes
        self.calls += other.calls
        self.urls += other.urls
        return self
