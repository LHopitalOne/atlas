"""RequestCollector: the base of every request idiom (fetch, axios, HTTP client methods)."""

from abc import abstractmethod

from .....core.http import Extraction
from ...kit import CallCollector
from ..clients.index import ClientIndex
from ..collector import FileCollector
from ..syntax.site import CallSite
from .builder import RequestBuilder
from .forwarding import Forwarder
from .pending import PendingRequest


class RequestCollector(CallCollector, FileCollector):
    """Walks the call sites of every file in source order and turns the ones it claims into requests. Each file's
    client classes are read with the same module, right after its requests; once every file is read, each request's
    client base path is put in front of its path, and a URL made of its function's parameters is settled at the calls
    that fill them in (Forwarder). Every pass starts with new modules and a new client index, so what
    a collector finds does not depend on what ran before it."""

    NAMES: frozenset[str] = frozenset()  # callee names of the idiom

    def start(self):
        self._pending = []
        self._opens = []
        self._clients = ClientIndex(self.workspace)

    def read(self, module):
        builder = RequestBuilder(self.workspace, module)
        for site in module.sites():
            try:
                self._pending += self.visit(builder, site)
            except RecursionError:  # pragma: no cover - pathological nesting
                continue
        self._opens += builder.opens
        self._clients.read(module)

    def finish(self) -> Extraction:
        clients, pending = self._clients.build(), self._pending + Forwarder(self.workspace).settle(self._opens)
        self.start()
        return Extraction(calls=[self._finished(p, clients) for p in pending])

    def visit(self, builder: RequestBuilder, site: CallSite) -> list[PendingRequest]:
        """The requests of a call site this collector claims; [] for the others."""
        return self.requests(builder, site) if self.claims(builder.module, site) else []

    def claims(self, module, site: CallSite) -> bool:
        """The site is a request of this idiom (its name is one of NAMES, and the call looks like one)."""
        return site.name in self.NAMES

    @abstractmethod
    def requests(self, builder: RequestBuilder, site: CallSite) -> list[PendingRequest]:
        """The requests a claimed call sends (none when its URL is unknown)."""

    def _finished(self, p: PendingRequest, clients):
        return self.call(p.source, p.line, p.full_path(clients), p.method, p.function, p.hints, test=p.test)
