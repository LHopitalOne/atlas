"""Use case: find the HTTP links between repositories by matching the requests each sends to the routes others serve.

Extractors (adapters) implement the `Extractor` port; this module never parses code or reads files. Each kind of
evidence is a LinkRule; LinkFinder asks the first rule that applies to a call.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..core.errors import AliasError
from ..core.evidence import Verification
from ..core.http import Call, Extraction, Route
from ..core.model import Status
from ..core.words import Words


@dataclass(frozen=True)
class Link:
    call: Call
    source: str  # repository that sends the request (for a payload call, the service that fetches the URL)
    target: str  # repository that serves (or should serve) the request
    route: Route | None  # None when nothing in the target serves it
    status: Status
    reason: str
    verification: Verification = Verification.UNVERIFIED  # set by LinkVerifier when a precise index is given
    verdicts: tuple = ()  # (Assumption, Verdict) for each name the call rests on


@dataclass(frozen=True)
class LinkReport:
    """Everything one run found: the links, and the extraction they came from, for the repositories asked about."""

    repos: list[str]
    extraction: Extraction
    links: list[Link]


class ServiceNames:
    """Turns hints into repository names: a repo's own name, or an alias (`upstream` -> `sentry`)."""

    def __init__(self, repos, aliases=None):
        self._names = {r.lower(): r for r in repos}
        self._aliases = {}
        for word, repo in (aliases or {}).items():
            if repo not in repos:
                raise AliasError(f'{word}={repo}', f'{repo} is not one of the repositories: {", ".join(repos)}')
            self._aliases[word.lower()] = repo

    def resolve(self, hints, exclude):
        found = set()
        for hint in hints:
            for word in Words.of(hint):
                repo = self._names.get(word) or self._aliases.get(word)
                if repo and repo != exclude:
                    found.add(repo)
        return found


class RouteIndex:
    """Routes by repository and by name, and which of them fit a request best."""

    def __init__(self, routes):
        self._by_repo = {}
        for r in routes:
            self._by_repo.setdefault(r.repo, []).append(r)
        self._by_name = {(r.repo, r.name): r for r in routes if r.name}

    def repos(self):
        return list(self._by_repo)

    def routes(self, repo):
        return self._by_repo.get(repo, [])

    def named(self, repo, name):
        return self._by_name.get((repo, name))

    def best(self, call, repo, stretch=False):
        """(top score, routes with it) among `repo`'s routes, leaving out catch-alls that would swallow literal
        segments of the call. With stretch, the call's last parameter may stand for several route segments."""
        scored = []
        for r in self.routes(repo):
            if not r.accepts(call.method) or call.path.swallowed_by(r.path):
                continue
            s = call.path.stretch_fit(r.path) if stretch else call.path.fit(r.path)
            if s is not None:
                scored.append((s, r))
        if not scored:
            return 0, []
        top = max(s for s, _ in scored)
        return top, [r for s, r in scored if s == top]

    def catch_all(self, call, repo):
        return next(
            (r for r in self.routes(repo) if r.accepts(call.method) and call.path.fit(r.path) is not None), None
        )


class LinkRule(ABC):
    """One kind of evidence that a call reaches another repository."""

    def __init__(self, names: ServiceNames, routes: RouteIndex):
        self._names = names
        self._routes = routes

    @abstractmethod
    def applies(self, call: Call) -> bool: ...

    @abstractmethod
    def links(self, call: Call) -> list[Link]: ...

    @staticmethod
    def _each(call, source, target, routes, status, reason):
        return [Link(call, source, target, r, status, reason) for r in routes]


class PayloadRule(LinkRule):
    """A URL to one of this repository's routes, handed to the services the hints name; they fetch it later."""

    def applies(self, call):
        return call.is_payload

    def links(self, call):
        route = self._routes.named(call.repo, call.route_name)
        if not route:
            return []
        targets = sorted(self._names.resolve(call.hints, exclude=call.repo))
        return [
            Link(call, t, call.repo, route, Status.INFERRED, f'{t} fetches a URL {call.repo} builds for it')
            for t in targets
        ]


class NamedTargetRule(LinkRule):
    """A request whose hints name the service it goes to."""

    def applies(self, call):
        return call.path is not None and bool(self._names.resolve(call.hints, exclude=call.repo))

    def links(self, call):
        return [lk for t in sorted(self._names.resolve(call.hints, exclude=call.repo)) for lk in self._to(call, t)]

    def _to(self, call, target):
        _, best = self._routes.best(call, target)
        if len(best) == 1:
            return self._each(call, call.repo, target, best, Status.MATCHED, 'named target, one route fits')
        if best:
            return self._each(call, call.repo, target, best, Status.AMBIGUOUS, f'{len(best)} routes fit equally')
        _, stretched = self._routes.best(call, target, stretch=True)
        if stretched:
            status = Status.INFERRED if len(stretched) == 1 else Status.AMBIGUOUS
            return self._each(
                call, call.repo, target, stretched, status, 'fits if its last parameter holds several segments'
            )
        catch_all = self._routes.catch_all(call, target)
        why = f'only the catch-all {catch_all.path} would take it' if catch_all else 'no route fits'
        return [Link(call, call.repo, target, None, Status.UNMATCHED, f'{target}: {why} ({call.method} {call.path})')]


class PathOnlyRule(LinkRule):
    """A request that names no service: it counts only if its path fits another repository's route literally and
    fits nothing in its own repository."""

    MIN_LITERALS = 2  # one fixed word ('/health') proves too little
    LITERAL_POINTS = 3  # what a literal-on-literal segment scores in PathTemplate.fit

    def applies(self, call):
        return call.path is not None and call.path.literals >= self.MIN_LITERALS

    def links(self, call):
        own, _ = self._routes.best(call, call.repo)
        candidates = []
        for repo in self._routes.repos():
            if repo == call.repo:
                continue
            top, best = self._routes.best(call, repo)
            if best and top >= self.LITERAL_POINTS * call.path.literals and top > own:
                candidates += [(repo, r) for r in best]
        status = Status.INFERRED if len(candidates) == 1 else Status.AMBIGUOUS
        return [
            Link(call, call.repo, t, r, status, 'no service named; the path fits this route') for t, r in candidates
        ]


class LinkFinder:
    """Matches every call against the routes of the other repositories."""

    RULES = (PayloadRule, NamedTargetRule, PathOnlyRule)  # asked in this order; the first that applies decides

    def __init__(self, repos, aliases=None, include_tests=False):
        self._names = ServiceNames(repos, aliases)
        self._include_tests = include_tests

    def find(self, extraction: Extraction) -> list[Link]:
        routes = RouteIndex(extraction.routes)
        rules = [rule(self._names, routes) for rule in self.RULES]
        links = []
        for call in extraction.calls:
            if call.test and not self._include_tests:
                continue
            rule = next((r for r in rules if r.applies(call)), None)
            if rule:
                links += rule.links(call)
        return links
