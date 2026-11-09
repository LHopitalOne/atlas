"""ChannelCollector: the channels other than HTTP that a repository sends and receives on (channels.table)."""

from .....core.http import Extraction
from ...kit import Collector
from .files import ModuleGraph
from .reader import ChannelReader
from .table import ENTRIES, GLOBAL, Form


class Needles:
    """Bytes a file must contain to use a library of the table (checked before parsing): the library's name in
    quotes, as an import or require names it, or the name of a browser global."""

    QUOTES = ("'", '"', '`')
    PREFIXES = ('', 'node:')

    @classmethod
    def of(cls, entries) -> tuple[bytes, ...]:
        found = {}
        for entry in entries:
            for library in entry.libraries:
                found.update(dict.fromkeys(cls._needles(entry, library)))
        return tuple(found)

    @classmethod
    def _needles(cls, entry, library):
        if library == GLOBAL:  # a global's methods are found through the global itself
            return [entry.callee.encode()] if entry.form in (Form.NEW, Form.CALL) else []
        return [f'{q}{p}{library}{q}'.encode() for q in cls.QUOTES for p in cls.PREFIXES]


class ChannelCollector(Collector):
    """Reads each file that names a library of the table (or one of its browser globals) with its own module, and
    the files its channel values come from as they are needed. Those are released once the file is read."""

    NEEDLES = Needles.of(ENTRIES)

    def collect(self) -> Extraction:
        graph = ModuleGraph(self.workspace)
        out = Extraction()
        for source in self.workspace.sources:
            if not source.mentions(*self.NEEDLES):
                continue
            module = self.workspace.module(source)
            try:
                out.extend(ChannelReader(self.workspace, graph.adopt(module)).read())
            except RecursionError:  # pragma: no cover - pathological nesting
                pass
            finally:
                graph.clear()
                module.release()
        return out
