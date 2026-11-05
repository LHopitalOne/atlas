"""Use case: find the HTTP links between repositories by matching the requests each sends to the routes others serve.

Extractors (adapters) implement the `Extractor` port; this module never parses code or reads files.
"""

import re
from dataclasses import dataclass
from typing import Protocol

from ..core.http import Call, Extraction, Route, methods_match, score, stretch_score, swallows_literals
from ..core.model import Status


class Extractor(Protocol):
    def extract(self, repo: str, root: str) -> Extraction: ...


@dataclass(frozen=True)
class Link:
    call: Call
    source: str  # repository that sends the request (for a payload call, the service that fetches the URL)
    target: str  # repository that serves (or should serve) the request
    route: Route | None  # None when nothing in the target serves it
    status: Status
    reason: str


def _words(text):
    """'SymbolicatorSession' / 'snuba_pool' / 'SENTRY_SNUBA' -> lower-case words."""
    spaced = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', text)
    return {w for w in re.split(r'[^a-z0-9]+', spaced.lower()) if w}


class ServiceNames:
    """Turns hints into repository names: a repo's own name, or an alias (`upstream` -> `sentry`)."""

    def __init__(self, repos, aliases=None):
        self.names = {r.lower(): r for r in repos}
        self.aliases = {a.lower(): r for a, r in (aliases or {}).items()}

    def resolve(self, hints, exclude):
        found = set()
        for h in hints:
            for w in _words(h):
                repo = self.names.get(w) or self.aliases.get(w)
                if repo and repo != exclude:
                    found.add(repo)
        return found


def find_links(extraction: Extraction, repos, aliases=None, include_tests=False):
    """Match every call against the routes of the other repositories. Returns a list of Link."""
    names = ServiceNames(repos, aliases)
    routes_by_repo = {}
    for r in extraction.routes:
        routes_by_repo.setdefault(r.repo, []).append(r)
    by_name = {(r.repo, r.name): r for r in extraction.routes if r.name}
    links = []
    for call in extraction.calls:
        if call.test and not include_tests:
            continue
        if call.kind == 'payload':
            links += _payload_links(call, by_name, names)
        else:
            links += _request_links(call, routes_by_repo, names)
    return links


def _payload_links(call, by_name, names):
    route = by_name.get((call.repo, call.route_name))
    if not route:
        return []
    return [
        Link(call, t, call.repo, route, Status.INFERRED, f'{t} fetches a URL {call.repo} builds for it')
        for t in sorted(names.resolve(call.hints, exclude=call.repo))
    ]


def _best(call, routes, fit=score):
    """The routes that fit the call best, leaving out catch-alls that would swallow literal segments of the call."""
    scored = [(fit(call.path, r.path), r) for r in routes if methods_match(call.method, r.methods)]
    scored = [(s, r) for s, r in scored if s is not None and not swallows_literals(call.path, r.path)]
    if not scored:
        return 0, []
    top = max(s for s, _ in scored)
    return top, [r for s, r in scored if s == top]


def _named_target_links(call, t, routes):
    top, best = _best(call, routes)
    if len(best) == 1:
        return [Link(call, call.repo, t, best[0], Status.MATCHED, 'named target, one route fits')]
    if best:
        return [Link(call, call.repo, t, r, Status.AMBIGUOUS, f'{len(best)} routes fit equally') for r in best]
    _, stretched = _best(call, routes, stretch_score)
    if stretched:
        status = Status.INFERRED if len(stretched) == 1 else Status.AMBIGUOUS
        return [
            Link(call, call.repo, t, r, status, 'fits if its last parameter holds several segments') for r in stretched
        ]
    catch_alls = [r for r in routes if methods_match(call.method, r.methods) and score(call.path, r.path) is not None]
    why = f'only the catch-all {catch_alls[0].path} would take it' if catch_alls else 'no route fits'
    return [Link(call, call.repo, t, None, Status.UNMATCHED, f'{t}: {why} ({call.method} {call.path})')]


def _request_links(call, routes_by_repo, names):
    if call.path is None:
        return []
    targets = names.resolve(call.hints, exclude=call.repo)
    if targets:
        return [lk for t in sorted(targets) for lk in _named_target_links(call, t, routes_by_repo.get(t, []))]
    # No hint names a service: only a call that fits a route literally, and fits none in its own repo, counts.
    if call.path.literals < 2:
        return []
    own, _ = _best(call, routes_by_repo.get(call.repo, []))
    candidates = []
    for repo, routes in routes_by_repo.items():
        if repo == call.repo:
            continue
        top, best = _best(call, routes)
        if best and top >= 3 * call.path.literals and top > own:
            candidates += [(repo, r) for r in best]
    status = Status.INFERRED if len(candidates) == 1 else Status.AMBIGUOUS
    return [Link(call, call.repo, t, r, status, 'no service named; the path fits this route') for t, r in candidates]
