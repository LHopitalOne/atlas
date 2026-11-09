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
from .addresses import AddressBook
from .bases import BaseHints


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
    """Turns hints into repository names: a repo's own name, an alias (`upstream` -> `sentry`), or what configuration
    says (AddressBook): an address, a host or a configured URL name."""

    def __init__(self, repos, aliases=None):
        self._names = {r.lower(): r for r in repos}
        self._phrases = {tuple(Words.ordered(r)): r for r in repos if len(Words.ordered(r)) > 1}
        self._aliases = {}
        for word, repo in (aliases or {}).items():
            if repo not in repos:
                raise AliasError(f'{word}={repo}', f'{repo} is not one of the repositories: {", ".join(repos)}')
            self._aliases[word.lower()] = repo
        self._book = AddressBook([], self.owner)

    def learn(self, urls):
        """Learn the addresses, hosts and URL names configuration gives (core.addresses.ServiceUrl)."""
        self._book = AddressBook(urls, self.owner)

    def owner(self, hints):
        """The one repository the hints' words name, or None when they name none or several."""
        found = self._by_words(hints)
        return found.pop() if len(found) == 1 else None

    def resolve(self, hints, exclude):
        found = self._by_words(hints)
        for hint in hints:
            found |= self._book.repos_for(hint)
        found.discard(exclude)
        return found

    def prefixes(self, repo):
        """API path prefixes ('/api/v1') configured URLs to `repo` carry."""
        return self._book.prefixes(repo)

    def _by_words(self, hints):
        found = set()
        for hint in hints:
            for word in Words.of(hint):
                repo = self._names.get(word) or self._aliases.get(word)
                if repo:
                    found.add(repo)
            found |= self._by_phrase(Words.ordered(hint))
        return found

    def _by_phrase(self, words):
        """Repositories with names of several words ('label-studio') whose words run together in the hint
        ('label_studio_sdk'). A name loses to a longer one whose first words run further in the hint:
        'label_studio_ml' starts 'label-studio-ml-backend', so it names neither."""
        hits = [p for p in self._phrases if self._runs(p, words)]
        return {self._phrases[p] for p in hits if not self._outrun(p, words)}

    def _outrun(self, phrase, words):
        n = len(phrase)
        return any(len(o) > n and o[:n] == phrase and self._runs(o[: n + 1], words) for o in self._phrases)

    @staticmethod
    def _runs(phrase, words):
        n = len(phrase)
        return any(tuple(words[i : i + n]) == phrase for i in range(len(words) - n + 1))


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

    def best_prefixed(self, call, repo, max_prefix, known=frozenset()):
        """(prefix, routes) that fit the call behind a few fixed leading segments ('.../api/v1'), or (None, []).
        Prefixes configuration gives for the repository (`known`) come first, then those the call's hints mention
        ('lms_coursemode_api_url' -> '/api/course_modes/v1'), then the shortest, then the best fit."""
        bases = BaseHints(call.hints)
        scored = []
        for r in self.routes(repo):
            if not r.accepts(call.method):
                continue
            found = call.path.prefixed_fit(r.path, max_prefix)
            if found is not None:
                points, prefix = found
                text = str(prefix)
                scored.append((text not in known, -bases.mentions(prefix), prefix.size, -points, text, r))
        if not scored:
            return None, []
        top = min(s[:5] for s in scored)
        return top[4], [s[5] for s in scored if s[:5] == top]

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
    """A request whose hints name the service it goes to. A route fits exactly, or with the request's last parameter
    standing for several segments, or behind a few fixed segments its base URL may carry ('/api/v1')."""

    MAX_PREFIX = 3  # fixed leading segments a base URL may hold: '/api', '/api/v1', '/api/courses/v1'

    def applies(self, call):
        return call.path is not None and bool(self._names.resolve(call.hints, exclude=call.repo))

    def links(self, call):
        return [lk for t in sorted(self._names.resolve(call.hints, exclude=call.repo)) for lk in self._to(call, t)]

    def _to(self, call, target):
        _, best = self._routes.best(call, target)
        prefix, prefixed = self._routes.best_prefixed(call, target, self.MAX_PREFIX, self._names.prefixes(target))
        if best and not (prefixed and BaseHints(call.hints).names_an_api() and not any(r.path.is_api for r in best)):
            if len(best) == 1:
                return self._each(call, call.repo, target, best, Status.MATCHED, 'named target, one route fits')
            return self._each(call, call.repo, target, best, Status.AMBIGUOUS, f'{len(best)} routes fit equally')
        _, stretched = self._routes.best(call, target, stretch=True)
        if stretched and not prefixed:
            status = Status.INFERRED if len(stretched) == 1 else Status.AMBIGUOUS
            return self._each(
                call, call.repo, target, stretched, status, 'fits if its last parameter holds several segments'
            )
        if prefixed:
            status = Status.INFERRED if len(prefixed) == 1 else Status.AMBIGUOUS
            return self._each(call, call.repo, target, prefixed, status, f'fits if the base URL ends in {prefix}')
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

    def __init__(self, repos, aliases=None, include_tests=False, rules=RULES):
        self._names = ServiceNames(repos, aliases)
        self._include_tests = include_tests
        self._rules = rules

    def find(self, extraction: Extraction) -> list[Link]:
        self._names.learn(extraction.urls)
        routes = RouteIndex(extraction.routes)
        rules = [rule(self._names, routes) for rule in self._rules]
        links = []
        for call in extraction.calls:
            if call.test and not self._include_tests:
                continue
            rule = next((r for r in rules if r.applies(call)), None)
            if rule:
                links += rule.links(call)
        return links
