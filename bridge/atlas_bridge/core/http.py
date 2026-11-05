"""Entities for HTTP links between services: path templates, routes a service serves, requests it sends.

Paths use one canonical syntax whatever the framework: `/rpc/{name}/{version}`, `{*rest}` for a tail wildcard.
Adapters translate Django regexes, Flask converters, axum captures and format strings into it.
"""

import re
from dataclasses import dataclass, field

ANY = 'ANY'
_PARAM = re.compile(r'^\{(\*?)([^{}]*)\}$')


@dataclass(frozen=True)
class Segment:
    text: str  # literal text, or the parameter's name
    kind: str = 'literal'  # 'literal' | 'param' | 'rest'

    def __str__(self):
        if self.kind == 'param' and '{' in self.text:  # partly dynamic, like 'v{version}'
            return self.text
        return {'literal': self.text, 'param': f'{{{self.text}}}', 'rest': f'{{*{self.text}}}'}[self.kind]


@dataclass(frozen=True)
class PathTemplate:
    segments: tuple[Segment, ...]

    @classmethod
    def parse(cls, path: str):
        """'/a/{b}/{*c}' -> segments. Empty segments (double or trailing slashes) are dropped."""
        segs = []
        for part in path.split('?')[0].split('/'):
            if not part:
                continue
            m = _PARAM.match(part)
            if m:
                segs.append(Segment(m.group(2) or 'param', 'rest' if m.group(1) else 'param'))
            elif '{' in part:  # partly dynamic, like 'v{version}': cannot be compared literally
                segs.append(Segment(part, 'param'))
            else:
                segs.append(Segment(part.lower()))
        return cls(tuple(segs))

    def __str__(self):
        return '/' + '/'.join(map(str, self.segments))

    @property
    def literals(self):
        return sum(s.kind == 'literal' for s in self.segments)


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


@dataclass(frozen=True)
class Call:
    """An HTTP request a repository sends, or a URL it hands to another service (kind='payload').

    hints: words near the request that may name the service it goes to (client and variable names, the class,
    the module path, the setting the base URL comes from). A payload call names the route it points at instead
    of a path, and its hints name the service that will fetch the URL.
    """

    repo: str
    file: str
    line: int
    path: PathTemplate | None
    method: str = ANY
    function: str = ''
    hints: frozenset[str] = frozenset()
    kind: str = 'request'  # 'request' | 'payload'
    route_name: str = ''
    test: bool = False  # only in tests, fixtures or tooling


def score(call: PathTemplate, route: PathTemplate):
    """How well a request path fits a route, or None if it cannot be served by it.

    Literal on literal must be equal (3 points). A parameter on either side matches one segment: parameter on
    parameter scores 2, a literal sent to a route parameter 1, a call parameter on a route literal 0 (possible, but
    proves little). A route's `{*rest}` takes every remaining segment. A route with fixed words must share at least
    one of them with the request: '/api/{id}/envelope' is not a request for '/{org}/issues/{id}'.
    """
    total = _fit(call, route)
    if total is None:
        return None
    shared = any(
        r.kind == 'literal' and i < len(call.segments) and call.segments[i].kind == 'literal'
        for i, r in enumerate(route.segments)
    )
    return total if shared or not any(r.kind == 'literal' for r in route.segments) else None


def _fit(call: PathTemplate, route: PathTemplate):
    total = 0
    for i, r in enumerate(route.segments):
        if r.kind == 'rest':
            return total
        if i >= len(call.segments):
            return None
        c = call.segments[i]
        if c.kind == 'rest':
            return total
        if r.kind == 'literal' and c.kind == 'literal':
            if r.text != c.text:
                return None
            total += 3
        elif r.kind == 'param' and c.kind == 'param':
            total += 2
        elif r.kind == 'param':
            total += 1
    return total if len(call.segments) == len(route.segments) else None


def swallows_literals(call: PathTemplate, route: PathTemplate):
    """True when the route's `{*rest}` takes literal segments the request names: a catch-all fallback (often a 404
    handler), not a route made for this request."""
    for i, r in enumerate(route.segments):
        if r.kind == 'rest':
            return any(c.kind == 'literal' for c in call.segments[i:])
    return False


def stretch_score(call: PathTemplate, route: PathTemplate):
    """Like score(), but the request's last segment, when it is a parameter, may stand for several route parameters:
    an id like 'partition/key' that holds a slash. None when that does not make it fit."""
    n = len(call.segments)
    if not n or call.segments[-1].kind != 'param' or len(route.segments) <= n:
        return None
    if any(r.kind != 'param' for r in route.segments[n - 1 :]):
        return None
    head = score(PathTemplate(call.segments[:-1]), PathTemplate(route.segments[: n - 1]))
    return None if head is None else head + 2


def methods_match(method: str, methods: frozenset[str]):
    return method == ANY or ANY in methods or method.upper() in methods


@dataclass
class Extraction:
    routes: list[Route] = field(default_factory=list)
    calls: list[Call] = field(default_factory=list)

    def extend(self, other: 'Extraction'):
        self.routes += other.routes
        self.calls += other.calls
        return self
