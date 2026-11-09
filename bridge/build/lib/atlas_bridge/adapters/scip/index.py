"""A SCIP index file: its documents by path, and where each symbol is defined."""

from ...core.errors import ScipFormatError
from .document import ScipDocument
from .schema import DocumentFields, IndexFields
from .wire import WireReader


class ScipIndex:
    """Reads only the document paths up front; a document's occurrences are decoded when it is first asked about,
    and the symbol -> definitions table only when a check needs to look beyond the assumed file."""

    def __init__(self, data: bytes, source: str = 'index'):
        self.source = source
        self._reader = WireReader(source)
        self._documents = {}
        for number, _, value in self._reader.fields(memoryview(data)):
            if number == IndexFields.DOCUMENTS:
                path = self._path(value)
                self._documents[path] = ScipDocument(path, value, self._reader)
        if not self._documents:
            raise ScipFormatError(source, 'it has no documents')
        self._definitions = None

    @classmethod
    def read(cls, path: str) -> 'ScipIndex':
        try:
            with open(path, 'rb') as f:
                return cls(f.read(), path)
        except OSError as e:
            raise ScipFormatError(path, e.strerror or str(e)) from e

    @property
    def paths(self):
        return list(self._documents)

    def document(self, path: str) -> ScipDocument | None:
        return self._documents.get(path)

    def at(self, path: str, line: int):
        doc = self._documents.get(path)
        return doc.at(line) if doc is not None else []

    def definitions(self, symbol: str) -> list[tuple[str, int]]:
        """(path, line) of every definition of a symbol in the indexed files."""
        if self._definitions is None:
            self._definitions = {}
            for doc in self._documents.values():
                for o in doc.definitions():
                    self._definitions.setdefault(o.symbol, []).append((doc.path, o.line))
        return self._definitions.get(symbol, [])

    def defined_in(self, symbol: str, path: str, start: int, end: int) -> bool:
        """Whether the symbol has a definition in `path` between lines start and end: no global table needed."""
        doc = self._documents.get(path)
        return doc is not None and any(o.symbol == symbol and start <= o.line <= end for o in doc.definitions())

    def _path(self, raw):
        for number, _, value in self._reader.fields(raw):
            if number == DocumentFields.RELATIVE_PATH:
                return bytes(value).decode('utf-8', 'replace')
        raise ScipFormatError(self.source, 'a document has no relative_path')
