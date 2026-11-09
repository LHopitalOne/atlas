"""ScipCallGraph: the CallGraph port answered from SCIP indexes of the services and the libraries read with them."""

from ...core.callgraph import Function, Site
from ...usecases.ports import CallGraph
from .index import ScipIndex
from .schema import SymbolRole
from .symbol import ScipSymbol


class ScipCallGraph(CallGraph):
    """Functions come from definitions that carry their body's lines (enclosing ranges). Callers are the references,
    in every index, to the functions the libraries define: a library's index writes its own module paths and each
    service's index the installed package's, so both are compared by ScipSymbol.key.
    """

    NOT_A_CALL = SymbolRole.DEFINITION | SymbolRole.IMPORT

    def __init__(self, indexes: dict[str, list[ScipIndex]], libraries):
        self._indexes = indexes
        self._libraries = frozenset(libraries)
        self._callers = None  # function key -> [Site], for the functions the libraries define

    def enclosing(self, repo: str, file: str, line: int) -> Function | None:
        best = None
        for index in self._indexes.get(repo, []):
            doc = index.document(file)
            for o in doc.definitions() if doc is not None else []:
                if ScipSymbol.is_callable(o.symbol) and o.encloses(line) and (best is None or o.start >= best.start):
                    best = o
        if best is None:
            return None
        return Function(ScipSymbol.key(best.symbol), ScipSymbol.name(best.symbol), repo, file, best.start, best.end)

    def callers(self, function: Function) -> list[Site]:
        if self._callers is None:
            self._callers = self._references(self._library_functions())
        return [s for s in self._callers.get(function.key, []) if not self._inside(s, function)]

    def _library_functions(self):
        keys = set()
        for repo in self._libraries:
            for index in self._indexes.get(repo, []):
                for path in index.paths:
                    doc = index.document(path)
                    keys.update(ScipSymbol.key(o.symbol) for o in doc.definitions() if ScipSymbol.is_callable(o.symbol))
        return keys

    def _references(self, wanted):
        """{key: [Site]}: every reference to a wanted function, in every index."""
        out = {}
        for repo, indexes in self._indexes.items():
            for index in indexes:
                for path in index.paths:
                    for o in index.document(path).occurrences():
                        key = self._called(o)
                        if key in wanted:
                            out.setdefault(key, []).append(Site(repo, path, o.line))
        return out

    def _called(self, o):
        """The key of the function or method an occurrence calls, or '' for anything else. A class reference
        (`Client(...)`) is not followed into `__init__` yet: a constructor's requests often sit behind conditions on its
        arguments (log in only without an API key) that the call graph cannot evaluate."""
        if o.roles & self.NOT_A_CALL or not ScipSymbol.is_callable(o.symbol):
            return ''
        return ScipSymbol.key(o.symbol)

    @staticmethod
    def _inside(site, function):
        """A recursive call, or the function naming itself: not a caller."""
        return site.repo == function.repo and site.file == function.file and function.start <= site.line <= function.end
