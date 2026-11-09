"""GeneratedClientRequests: the requests of generated API clients, settled at the calls of their functions."""

from .....core.http import Extraction
from ...kit import CallCollector
from ..calls.forwarding import Forwarder
from ..collector import FileCollector
from .requests import GeneratedRequests


class GeneratedClientRequests(CallCollector, FileCollector):
    """A request sent through a generated client's runtime (generated.runtime) is a request of its function; one
    whose path holds the function's parameters (`getPet({ id })`) is settled at the calls that fill them in, like
    any other request wrapper (Forwarder)."""

    def start(self):
        self._pending = []
        self._opens = []

    def read(self, module):
        closed, opened = GeneratedRequests.read(self.workspace, module)
        self._pending += closed
        self._opens += opened

    def finish(self) -> Extraction:
        pending = self._pending + Forwarder(self.workspace).settle(self._opens)
        self.start()
        return Extraction(
            calls=[self.call(p.source, p.line, p.path, p.method, p.function, p.hints, test=p.test) for p in pending]
        )
