"""KeyedRequests: data fetching hooks whose key is the URL they fetch (`useSWR('/api/notes')`)."""

from .....core.http import Extraction, Protocol
from ...kit import CallCollector
from ..collector import FileCollector
from ..syntax.nodes import JsSyntax
from .builder import RequestBuilder
from .forwarding import Forwarder
from .libraries import EntryPoints


class KeyedRequests(CallCollector, FileCollector):
    """A hook of libraries.EntryPoints that fetches its key with a fetcher (SWR's `useSWR(key)` with the SWRConfig
    fetcher or `useSWR(key, fetcher)`, TanStack Query's `useQuery({ queryKey })` with the default queryFn) sends a
    GET to that key. The key may be a const, a conditional key (`id ? `/api/notes/${id}` : null`), an array whose
    first item is the URL, or a function that returns it. Only a key that reads as a path or URL is a request; a key
    made of a hook's parameters is settled at the hook's callers (Forwarder)."""

    FUNCTIONS = frozenset({'arrow_function', 'function_expression', 'function'})

    def start(self):
        self._pending = []
        self._opens = []

    def read(self, module):
        builder = RequestBuilder(self.workspace, module)
        for call, entry in EntryPoints.calls_in(module, Protocol.HTTP):
            key = self._url(entry.channel(JsSyntax.args(call)))
            if key is not None:
                self._pending += builder.build(call, None, key, 'GET', require_path=True)
        self._opens += builder.opens

    def finish(self) -> Extraction:
        pending = self._pending + Forwarder(self.workspace).settle(self._opens)
        self.start()
        return Extraction(
            calls=[self.call(p.source, p.line, p.path, p.method, p.function, p.hints, test=p.test) for p in pending]
        )

    @classmethod
    def _url(cls, key):
        """The expression of a key that holds the URL: the key, the first item of an array key, or what a key
        function returns."""
        key = JsSyntax.unwrap(key)
        if key is not None and key.type in cls.FUNCTIONS:
            body = JsSyntax.unwrap(key.child_by_field_name('body'))
            key = body if body is not None and body.type != 'statement_block' else None
        if key is not None and key.type == 'array':
            items = [i for i in key.named_children if i.type != 'comment']
            key = JsSyntax.unwrap(items[0]) if items else None
        return key
