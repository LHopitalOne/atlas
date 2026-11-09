"""Use case: requests a client library sends on its callers' behalf, moved to the lines in the services that call
into the library."""

from dataclasses import replace

from ..core.callgraph import Function, Site
from ..core.evidence import Assumption
from ..core.http import Call
from .ports import CallGraph


class LibraryHops:
    """A library read alongside the services (a client SDK) sends requests for them: `ls.tasks.get(id)` in a service
    runs `RawTasksClient.get` in the SDK, which sends `GET /api/tasks/{id}/`. From the function each library request is
    in, the call graph is walked up, through the library's own functions, to the lines in service repositories that
    call into it; the request is reported there. Every call followed becomes an assumption a precise index can check.
    """

    MAX_DEPTH = 6  # library functions between the request and the service's call
    MAX_SITES = 400  # service lines one library request is moved to
    MIN_LITERALS = 2  # a library request moved this far must know its path ('/data/{x}' fits too many routes)

    def __init__(self, graph: CallGraph, libraries):
        self._graph = graph
        self._libraries = frozenset(libraries)

    def calls(self, calls: list[Call]) -> list[Call]:
        """The library requests among `calls`, each at every service line that reaches it."""
        out = []
        for call in calls:
            if call.repo in self._libraries and self._known(call):
                out += self._moved(call)
        return list(dict.fromkeys(out))

    def _known(self, call):
        return (
            not call.is_payload and not call.test and call.path is not None and call.path.literals >= self.MIN_LITERALS
        )

    def _moved(self, call):
        start = self._graph.enclosing(call.repo, call.file, call.line)
        if start is None:
            return []
        out, seen, frontier = [], {start.key}, [(start, ())]
        for _ in range(self.MAX_DEPTH):
            frontier = self._step(call, frontier, seen, out)
            if not frontier or len(out) >= self.MAX_SITES:
                break
        return out[: self.MAX_SITES]

    def _step(self, call, frontier, seen, out):
        """One level up: service lines go to `out`, library functions that call this level come back."""
        upper = []
        for function, chain in frontier:
            for site in self._graph.callers(function):
                followed = (self._assumption(site, function), *chain)
                if site.repo not in self._libraries:
                    out.append(self._at(call, site, function, followed))
                    continue
                up = self._graph.enclosing(site.repo, site.file, site.line)
                if up is not None and up.key not in seen:
                    seen.add(up.key)
                    upper.append((up, followed))
        return upper

    def _assumption(self, site: Site, function: Function) -> Assumption:
        """That the call at `site` runs `function`: in the library, its repository is named."""
        return Assumption(
            site.file,
            site.line,
            function.name,
            function.file,
            function.start,
            function.end,
            repo=site.repo if site.repo in self._libraries else '',
            target_repo=function.repo,
        )

    def _at(self, call: Call, site: Site, function: Function, followed) -> Call:
        caller = self._graph.enclosing(site.repo, site.file, site.line)
        return replace(
            call,
            repo=site.repo,
            file=site.file,
            line=site.line,
            function=caller.name if caller is not None else '',
            hints=call.hints | {function.name, call.repo},  # a client library's name often names its service
            assumptions=followed,
        )
