"""GraphqlCalls: the GraphQL operations a repository sends, one call per root field."""

from ......core.http import ANY, Extraction, Protocol
from ....kit import CallCollector, UrlTemplate
from ...collector import FileCollector
from ...syntax.functions import Functions
from ...syntax.nodes import JsSyntax
from ..builder import RequestBuilder
from ..libraries import EntryPoints
from .document import GraphqlDocument
from .forward import DocumentForwarder, OpenDocument
from .text import DocumentText
from .transport import GraphqlBody


class GraphqlCalls(CallCollector, FileCollector):
    """An operation `query Rooms { rooms { id } }` sent to a GraphQL server is a call to '/rooms' over GRAPHQL, one
    per root field, wherever its document is given to what sends it:

    - an HTTP request posting `{ query }` (GraphqlBody), with the document written there or held in a constant of
      this file or another; when the document is a parameter of a helper (`gql(query, variables)`), at each call of
      the helper that gives one (DocumentForwarder);
    - a GraphQL client entry point (libraries.EntryPoints: Apollo and urql hooks, graphql-request).

    Fragment definitions in a document, and fragments interpolated into it, add no root fields.
    """

    def start(self):
        self._calls = []
        self._opens = []

    def read(self, module):
        for site in module.sites():
            if site.name in GraphqlBody.NAMES:
                self._transport(module, site)
        for call, entry in EntryPoints.calls_in(module, Protocol.GRAPHQL):
            operations = self._operations(module, entry.channel(JsSyntax.args(call)))
            name = JsSyntax.text(call.child_by_field_name('function'))
            self._calls += self.emit(module, call, operations, {name, *entry.libraries[:1]})

    def finish(self) -> Extraction:
        settled = DocumentForwarder(self.workspace, self.emit).settle(self._opens)
        calls, self._calls, self._opens = self._calls + settled, [], []
        return Extraction(calls=calls)

    def emit(self, module, node, operations, hints) -> list:
        """One GRAPHQL call per root field of the operations, at `node`."""
        function, owner = Functions.enclosing(node)
        test = self.workspace.is_test(module.source, node)
        out = []
        for op in operations:
            names = set(hints) | {h for h in (function, owner, module.path, op.name) if h}
            names = frozenset(h[: RequestBuilder.MAX_HINT] for h in names)
            for field in op.fields:
                path = '/' + field
                line = JsSyntax.line(node)
                out.append(self.call(module.source, line, path, ANY, function, names, test, protocol=Protocol.GRAPHQL))
        return out

    def _transport(self, module, site):
        query = GraphqlBody.document(module, site)
        if query is None:
            return
        hints = set()
        url = GraphqlBody.url(site)
        if url is not None:
            hints.update(UrlTemplate.split(module.values.resolve(url, hints)).hints)
        operations = self._operations(module, query)
        if operations:
            self._calls += self.emit(module, site.node, operations, hints)
            return
        param = DocumentText.parameter(module, query)
        if param is not None:
            self._opens.append(OpenDocument.at(module, param[0], param[1], site.node, hints))

    @staticmethod
    def _operations(module, node):
        text = DocumentText.of(module, node) if node is not None else None
        return GraphqlDocument(text).operations() if text else []
