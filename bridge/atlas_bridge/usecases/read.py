"""Use case: find the requests and routes the extractors miss by letting a language model read the files they leave
unexplained, then check every claim against the code and match it with the same rules as anything else."""

from dataclasses import dataclass, replace
from typing import NamedTuple

from ..core.evidence import Verification
from ..core.http import Extraction
from ..core.model import Status
from .link import Link, LinkFinder
from .ports import RequestReader, SourceFiles
from .readfiles import ReadFiles
from .reading import ReadCheck


@dataclass(frozen=True)
class ReadReport:
    """What a reading pass did: files read (and read again with helpers), requests claimed and borne out by the
    code, routes borne out, and how many requests became links."""

    files: int = 0
    again: int = 0
    claimed: int = 0
    checked: int = 0
    routes: int = 0
    linked: int = 0


class ReadFinders(NamedTuple):
    """The rules of the run (for the requests the extractors found, meeting routes a reader found), and those for
    requests a reader found (they may reach their own repository from any file: within.ReadWithinRule)."""

    own: LinkFinder
    read: LinkFinder


class ReadLinks:
    """1. Asks the reader about the files ReadFiles picks: the requests each sends, the helpers it defines, and the
    routes, jobs and message handlers it serves.
    2. Keeps each claim the code bears out (ReadCheck): requests not at one the extractors already linked, routes
    not at one they already read.
    3. Matches the requests read, and the extractors' requests left open, against every route, the ones read
    included: the reader proposes, the rules decide. Only links the rules settle that rest on something read are
    kept, marked read and never stronger than inferred; an open link left at the same line gives way.
    4. Reads again the files that call a helper, and matches what that adds the same way."""

    NEAR = 2  # lines between two claims about one request or route for them to be the same
    SETTLED = frozenset({Status.MATCHED, Status.INFERRED, Status.OUTSIDE})
    OPEN = frozenset({Status.AMBIGUOUS, Status.UNMATCHED})

    def __init__(self, reader: RequestReader, sources: SourceFiles, finders: ReadFinders, repos: list[str]):
        self._reader = reader
        self._finders = finders
        self._files = ReadFiles(sources, repos)
        self._check = ReadCheck()
        self.report = ReadReport()

    def refine(self, links: list[Link], extraction: Extraction) -> list[Link]:
        settled = self._sites(link.call for link in links if link.status in self.SETTLED)
        first = self._files.first(self._count(settled), self._count(self._sites(extraction.routes)))
        readings = self._read(first)
        read_routes = self._routes(readings.values(), extraction.routes)
        everything = Extraction(list(extraction.routes) + read_routes, [], list(extraction.urls))
        kept, claimed, checked = self._requests(readings.values(), settled, everything)
        kept += self._reached(extraction, settled | self._sites(lk.call for lk in kept), everything, read_routes)
        again = self._files.again(first, [r for _, r in readings.values()], self._functions(links + kept))
        settled |= self._sites(link.call for link in kept)
        more, claimed_again, checked_again = self._requests(self._read(again).values(), settled, everything)
        kept += more
        sites = self._sites(link.call for link in kept)
        out = [link for link in links if not (link.status in self.OPEN and self._near(link.call, sites))]
        self.report = ReadReport(
            len(first),
            len(again),
            claimed + claimed_again,
            checked + checked_again,
            len(read_routes),
            len({link.call for link in kept}),
        )
        return out + kept

    def _read(self, cases):
        """{(repo, path): (case, reading)}."""
        found = self._reader.read(cases) if cases else []
        return {(c.repo, c.path): (c, r) for c, r in zip(cases, found, strict=True)}

    def _routes(self, readings, known):
        """The routes read that the code bears out and the extractors did not read."""
        sites, found = self._sites(known), []
        for case, reading in readings:
            for claim in reading.routes if reading else ():
                route = self._check.route(case, claim)
                if route is not None and not self._near(route, sites):
                    found.append(route)
        return list(dict.fromkeys(found))

    def _requests(self, readings, settled, everything):
        """(links the rules settle for the requests read that the code bears out, claims made, claims borne out)."""
        claimed, calls = 0, []
        for case, reading in readings:
            for request in reading.requests if reading else ():
                claimed += 1
                call = self._check.call(case, request)
                if call is not None and not self._near(call, settled):
                    calls.append(call)
        calls = list(dict.fromkeys(calls))
        found = self._finders.read.find(replace(everything, calls=calls))
        return [self._marked(link, 'request') for link in found if self._settles(link)], claimed, len(calls)

    def _reached(self, extraction, settled, everything, read_routes):
        """Links the rules settle from the extractors' open requests to the routes read."""
        if not read_routes:
            return []
        calls = [c for c in dict.fromkeys(extraction.calls) if not self._near(c, settled)]
        found = self._finders.own.find(replace(everything, calls=calls))
        new = set(read_routes)
        return [self._marked(link, 'route') for link in found if self._settles(link) and link.route in new]

    def _functions(self, links):
        """(repo, file, function name) of each function a settled request is sent from."""
        return {
            (lk.call.repo, lk.call.file, lk.call.function.split('.')[-1])
            for lk in links
            if lk.status in self.SETTLED and lk.call.function
        }

    def _settles(self, link):
        return link.status in self.SETTLED and (link.route is not None or link.status == Status.OUTSIDE)

    def _marked(self, link, what):
        status = Status.INFERRED if link.status == Status.MATCHED else link.status
        model = self._reader.model or 'a language model'
        why = f'{model} read the {what} in the code, and the code bore it out; {link.reason}'
        return replace(link, status=status, reason=why, verification=Verification.READ)

    @staticmethod
    def _sites(items):
        return {(i.repo, i.file, i.line) for i in items}

    @staticmethod
    def _count(sites):
        counts = {}
        for repo, file, _ in sites:
            counts[repo, file] = counts.get((repo, file), 0) + 1
        return counts

    def _near(self, item, sites):
        return any((item.repo, item.file, item.line + d) in sites for d in range(-self.NEAR, self.NEAR + 1))
