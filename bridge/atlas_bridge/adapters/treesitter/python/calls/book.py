"""The calls one collector found, one per site, path, method and kind; repeated findings merge their hints."""

from .....core.http import ANY, Call, PathTemplate
from ..syntax import PythonSyntax
from ..values import Marker


class CallBook:
    """Calls keyed by (file, line, path, method, kind, route name). A request settled at the same site through
    several wrappers is one call whose hints are the union of what each found."""

    def __init__(self, collector):
        self._collector = collector  # the CallCollector whose call() factory builds each Call
        self._calls = {}

    def add(self, scope, site, path, method=ANY, hints=(), assumptions=(), kind=Call.REQUEST, route_name=''):
        source = scope.source
        line = PythonSyntax.line(site)
        template = PathTemplate.parse(path) if path is not None else None
        key = (source.path, line, str(template), method, kind, route_name)
        merged = frozenset(h for h in hints if h and not Marker.is_unresolved(h))
        old = self._calls.get(key)
        if old is not None:
            merged = merged | old.hints
            assumptions = (*old.assumptions, *assumptions)
        assumptions = tuple(sorted(set(assumptions), key=self._order))
        test = self._collector.workspace.is_test(source, site)
        self._calls[key] = self._collector.call(
            source,
            line,
            path,
            method,
            scope.qualified,
            merged,
            test=test,
            kind=kind,
            route_name=route_name,
            assumptions=assumptions,
        )

    @staticmethod
    def _order(a):
        return (a.file, a.line, a.name, a.target_file, a.target_start, a.target_end)

    def calls(self) -> list[Call]:
        """The calls in key order (file, line, path, method, kind, route name), the same on every run."""
        return [self._calls[key] for key in sorted(self._calls)]
