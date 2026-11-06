"""One SCIP document (a source file): its occurrences, decoded on first use and indexed by line."""

from typing import NamedTuple

from .schema import DocumentFields, OccurrenceFields, RangeFields, SymbolRole
from .wire import WireReader


class Occurrence(NamedTuple):
    """A symbol appearing on a line (1-based), as a definition or a reference."""

    line: int
    symbol: str
    roles: int

    @property
    def is_definition(self):
        return bool(self.roles & SymbolRole.DEFINITION)


class ScipDocument:
    def __init__(self, path: str, raw, reader: WireReader):
        self.path = path
        self._raw = raw  # the encoded Document message, decoded on first use
        self._reader = reader
        self._by_line = None

    def at(self, line: int) -> list[Occurrence]:
        return self._lines().get(line, [])

    def definitions(self):
        """Every definition in the file."""
        return [o for occurrences in self._lines().values() for o in occurrences if o.is_definition]

    def _lines(self):
        if self._by_line is None:
            self._by_line = {}
            for number, _, value in self._reader.fields(self._raw):
                if number == DocumentFields.OCCURRENCES:
                    o = self._occurrence(value)
                    if o is not None:
                        self._by_line.setdefault(o.line, []).append(o)
            self._raw = None
        return self._by_line

    def _occurrence(self, raw):
        line, symbol, roles = None, '', 0
        for number, wire, value in self._reader.fields(raw):
            if number == OccurrenceFields.RANGE:
                line = self._reader.ints(wire, value)[0]
            elif number in (OccurrenceFields.SINGLE_LINE_RANGE, OccurrenceFields.MULTI_LINE_RANGE):
                line = self._start_line(value)
            elif number == OccurrenceFields.SYMBOL:
                symbol = bytes(value).decode('utf-8', 'replace')
            elif number == OccurrenceFields.SYMBOL_ROLES:
                roles = value
        return Occurrence(line + 1, symbol, roles) if line is not None and symbol else None  # SCIP lines are 0-based

    def _start_line(self, raw):
        for number, _, value in self._reader.fields(raw):
            if number == RangeFields.START_LINE:
                return value
        return 0  # proto3 leaves a zero line out
