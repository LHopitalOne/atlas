"""ScipReferences: the ReferenceIndex port answered from SCIP indexes of the repositories on a map."""

from ...core.references import Definition, Use
from ...usecases.ports import ReferenceIndex
from .index import ScipIndex
from .schema import SymbolRole
from .symbol import ScipSymbol


class ScipReferences(ReferenceIndex):
    """A use is an occurrence that is not a definition or an import, of a named, non-local symbol. The definition a
    use sits in is the innermost function or class whose enclosing range holds its line (indexers that write no
    enclosing ranges leave it None). A use's key is its exact symbol; its definition is the one with that symbol, else
    the only one of the same package with the same descriptors (ScipSymbol.key): a service's use of a library read
    alongside, whose package version differs, reaches the library's own definition, but `serde_json::Value` never
    reaches another crate's `Value`, nor a name defined in several places any of them."""

    NOT_A_USE = SymbolRole.DEFINITION | SymbolRole.IMPORT
    TYPE = '#'  # a type descriptor ends in '#'

    def __init__(self, indexes: dict[str, list[ScipIndex]]):
        self._indexes = indexes
        self._definitions = None  # exact symbol -> Definition
        self._by_key = None  # ScipSymbol.key -> [Definition], for uses whose exact symbol no index defines

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
                out.append(Use(o.line, o.symbol, self._definition(repo, file, inner.get(o.line))))
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
            self._load()
        found = self._definitions.get(key)
        if found is not None:
            return found
        package = ScipSymbol.package(key)
        same = [d for d, p in self._by_key.get(ScipSymbol.key(key), []) if p == package]
        return same[0] if len(same) == 1 else None

    def _load(self):
        self._definitions, self._by_key = {}, {}
        for repo, indexes in sorted(self._indexes.items()):
            for index in indexes:
                for path in index.paths:
                    for o in index.document(path).definitions():
                        if ScipSymbol.name(o.symbol) and o.symbol not in self._definitions:
                            found = self._definition(repo, path, o)
                            self._definitions[o.symbol] = found
                            self._by_key.setdefault(found.key, []).append((found, ScipSymbol.package(o.symbol)))

    def _is_scope(self, symbol):
        return ScipSymbol.is_callable(symbol) or symbol.endswith(self.TYPE)

    @staticmethod
    def _definition(repo, file, occurrence):
        if occurrence is None:
            return None
        symbol = occurrence.symbol
        return Definition(ScipSymbol.key(symbol), ScipSymbol.name(symbol), repo, file, occurrence.line)
