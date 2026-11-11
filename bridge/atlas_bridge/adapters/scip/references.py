"""ScipReferences: the ReferenceIndex port answered from SCIP indexes of the repositories on a map."""

from ...core.references import Definition, Use
from ...usecases.ports import ReferenceIndex
from .index import ScipIndex
from .schema import SymbolRole
from .symbol import ScipSymbol


class ScipReferences(ReferenceIndex):
    """A use is an occurrence that is not a definition or an import, of a named, non-local symbol. The definition a
    use sits in is the innermost function or class whose enclosing range holds its line (indexers that write no
    enclosing ranges leave it None). Definitions are found by ScipSymbol.key in every index, so a service's use of a
    library read alongside reaches the library's own definition."""

    NOT_A_USE = SymbolRole.DEFINITION | SymbolRole.IMPORT
    TYPE = '#'  # a type descriptor ends in '#'

    def __init__(self, indexes: dict[str, list[ScipIndex]]):
        self._indexes = indexes
        self._definitions = None  # key -> Definition

    def files(self, repo: str) -> frozenset[str]:
        return frozenset(p for index in self._indexes.get(repo, []) for p in index.paths)

    def uses(self, repo: str, file: str) -> list[Use]:
        out = []
        for index in self._indexes.get(repo, []):
            doc = index.document(file)
            if doc is None:
                continue
            inner = self._innermost(doc)
            for o in doc.occurrences():
                if o.roles & self.NOT_A_USE or not ScipSymbol.name(o.symbol):
                    continue
                out.append(Use(o.line, ScipSymbol.key(o.symbol), self._definition(repo, file, inner.get(o.line))))
        return out

    def _innermost(self, doc):
        """{line: the innermost function or class definition around it}: spans laid down outermost first, so a
        nested one overwrites the lines it covers."""
        spans = sorted((o for o in doc.definitions() if o.end and self._is_scope(o.symbol)), key=lambda o: o.start)
        inner = {}
        for span in spans:
            for line in range(span.start, span.end + 1):
                inner[line] = span
        return inner

    def definition(self, key: str) -> Definition | None:
        if self._definitions is None:
            self._definitions = {}
            for repo, indexes in sorted(self._indexes.items()):
                for index in indexes:
                    for path in index.paths:
                        for o in index.document(path).definitions():
                            if ScipSymbol.name(o.symbol):
                                found = self._definition(repo, path, o)
                                self._definitions.setdefault(found.key, found)
        return self._definitions.get(key)

    def _is_scope(self, symbol):
        return ScipSymbol.is_callable(symbol) or symbol.endswith(self.TYPE)

    @staticmethod
    def _definition(repo, file, occurrence):
        if occurrence is None:
            return None
        symbol = occurrence.symbol
        return Definition(ScipSymbol.key(symbol), ScipSymbol.name(symbol), repo, file, occurrence.line)
