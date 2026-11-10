"""Use case: settle the requests the rules leave open by letting a decision model choose among the routes that fit."""

from dataclasses import dataclass

from ..core.evidence import Verification
from ..core.http import Call, Extraction
from ..core.model import Status
from .link import Link, RouteIndex
from .ports import Choice, JudgeCase, RouteJudge


@dataclass(frozen=True)
class JudgeReport:
    """What a judging pass did: how many requests were asked about, and how many got a route."""

    asked: int
    settled: int


class JudgedLinks:
    """For each request with no link, or only an ambiguous or unmatched one, the code gathers the few routes that
    could take it (those that fit its path in any repository, also behind a prefix the code does not show); a judge
    reads the lines around the call and picks one, or none. A pick it is sure of (THRESHOLD) becomes an inferred link
    marked judged; anything else keeps what the rules said. The judge only selects among what the code offers, so it
    never invents a route, and requests the rules settled are never asked about."""

    THRESHOLD = 0.8  # how sure the judge must be for its pick to become a link
    MAX_CANDIDATES = 8  # more routes than this fit: the path says too little to choose by reading the code
    MAX_PREFIX = 3  # fixed segments a base URL may add in front of the path ('/api/v1')
    MAX_CASES = 1000  # requests asked about in one run, to bound the cost
    MIN_SHARED = 2  # fixed words a route must share with the path to be offered on similarity alone
    OPEN = frozenset({Status.AMBIGUOUS, Status.UNMATCHED})

    def __init__(self, judge: RouteJudge, include_tests: bool = False, within: bool = False):
        """within: also offer a request its own repository's routes, as the rules do with --within."""
        self._judge = judge
        self._include_tests = include_tests
        self._within = within
        self.report = JudgeReport(0, 0)

    def refine(self, links: list[Link], extraction: Extraction) -> list[Link]:
        routes = RouteIndex(extraction.routes)
        by_call = {}
        for link in links:
            by_call.setdefault(link.call, []).append(link)
        cases = []
        for call in dict.fromkeys(extraction.calls):
            if self._open(call, by_call.get(call, [])):
                candidates = self._candidates(call, by_call.get(call, []), routes)
                if 0 < len(candidates) <= self.MAX_CANDIDATES:
                    cases.append(JudgeCase(call, candidates))
        cases = cases[: self.MAX_CASES]
        choices = self._judge.choose(cases) if cases else []
        settled = {}
        for case, choice in zip(cases, choices, strict=True):
            link = self._link(case, choice)
            if link is not None:
                settled[case.call] = link
        self.report = JudgeReport(len(cases), len(settled))
        out = [link for link in links if link.call not in settled]
        return out + list(settled.values())

    def _open(self, call: Call, links: list[Link]) -> bool:
        if call.path is None or not call.path.literals or call.is_payload or call.host:
            return False
        if call.test and not self._include_tests:
            return False
        return all(link.status in self.OPEN for link in links)

    def _candidates(self, call, links, routes):
        """The routes the rules saw fit, those that fit with a stretch or behind a prefix, then those that share the
        most fixed words with the path ('/json/{*base}/billing/plan' and '/json/billing/plan'), up to MAX_CANDIDATES."""
        found = [link.route for link in links if link.route is not None]
        for repo in self._repos(call, routes):
            found += routes.best(call, repo, stretch=True)[1]
            found += routes.best_prefixed(call, repo, self.MAX_PREFIX)[1]
        found = list(dict.fromkeys(found))
        if len(found) < self.MAX_CANDIDATES:
            found += [r for r in self._similar(call, routes) if r not in found][: self.MAX_CANDIDATES - len(found)]
        return tuple(found)

    def _similar(self, call, routes):
        """Routes of the call's protocol and method sharing at least MIN_SHARED fixed words with its path (all of them
        when the path has fewer), most shared first, then fewest words of their own."""
        words = self._words(call.path)
        least = min(self.MIN_SHARED, len(words))
        scored = []
        for repo in self._repos(call, routes):
            for r in routes.routes(repo):
                if r.protocol != call.protocol or not r.accepts(call.method):
                    continue
                own = self._words(r.path)
                shared = len(words & own)
                if shared >= least and shared:
                    scored.append((-shared, len(own - words), r.repo, str(r.path), r))
        scored.sort(key=lambda t: t[:4])
        return [t[4] for t in scored]

    def _repos(self, call, routes):
        """The repositories whose routes a request may reach: the others, and its own only with `within`."""
        return [r for r in routes.repos() if r != call.repo or self._within]

    @staticmethod
    def _words(path):
        return {s.text.lower() for s in path.segments if s.is_literal}

    def _link(self, case: JudgeCase, choice: Choice):
        if choice.index is None or choice.probability < self.THRESHOLD:
            return None
        route = case.candidates[choice.index]
        why = (
            f'the code leaves {len(case.candidates)} routes open; a decision model read the call and chose this one '
            f'(p={choice.probability:.2f})'
        )
        return Link(case.call, case.call.repo, route.repo, route, Status.INFERRED, why, Verification.JUDGED)
