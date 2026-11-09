"""Settling the requests of package functions in the application: where it calls them, and where it passes them on."""

from .....core.http import ANY
from ...kit import UrlTemplate
from ..calls.forwarding import Forwarder
from ..calls.pending import PendingRequest
from ..module import JsModule
from ..syntax.functions import Functions
from ..syntax.nodes import JsSyntax
from ..values.urls import UrlText


class PackageForwarder(Forwarder):
    """A Forwarder whose open requests may come from a package: such a request (its path is the import specifier)
    is settled at the calls of a file that imports its function from that specifier, by the same name. A request
    opened again in the application (a wrapper of the package function) is followed as any other."""

    def __init__(self, workspace, specifiers):
        super().__init__(workspace)
        self._specifiers = frozenset(specifiers)

    def _imports(self, module, open_):
        if open_.path not in self._specifiers:
            return Forwarder._imports(module, open_)
        return module.imports.get(open_.function) == (open_.path, open_.function)


class PassedFunctions:
    """A package function handed on as a value (`asMutation(deleteSession, ...)`, `{ mutationFn: deleteSession }`)
    sends its request from wherever it is later called with arguments not seen here: it is reported where it is
    handed on, with its parameters left as parameters ('/sessions/{id}')."""

    HANDED_ON = frozenset({'arguments', 'pair', 'array'})  # where a function value is passed to other code
    NAMES = 'identifier'

    def __init__(self, workspace, opens):
        self._workspace = workspace
        self._by_name = {}
        for open_ in opens:
            self._by_name.setdefault(open_.function, []).append(open_)

    def requests(self) -> list[PendingRequest]:
        out = []
        needles = tuple(n.encode() for n in self._by_name)
        for source in self._workspace.sources:
            if not needles or not source.mentions(*needles):
                continue
            module = JsModule(source)
            for node in JsSyntax.walk(source.root, {self.NAMES}):
                for open_ in self._handed_on(module, node):
                    out += self._pending(module, node, open_)
            module.release()
        return out

    def _handed_on(self, module, node):
        opens = self._by_name.get(JsSyntax.text(node), ())
        parent = node.parent
        if not opens or parent is None or parent.type not in self.HANDED_ON:
            return []
        if parent.type == 'pair' and parent.child_by_field_name('value') != node:
            return []
        if module.scopes.binding(node, JsSyntax.text(node)) is not None:
            return []  # a local of the same name
        return [o for o in opens if module.imports.get(o.function) == (o.path, o.function)]

    def _pending(self, module, node, open_):
        url = UrlTemplate.split(UrlText.with_params(open_.template))
        if url.path is None or not UrlText.matchable(open_.template) or not UrlText.path_like(open_.template):
            return []
        function, owner = Functions.enclosing(node)
        hints = set(open_.hints) | set(url.hints) | {open_.function, module.path} | {h for h in (function, owner) if h}
        method = ANY if UrlText.PLACEHOLDER.fullmatch(open_.method) else open_.method
        test = self._workspace.is_test(module.source, node)
        line = JsSyntax.line(node)
        return [PendingRequest(module.source, line, method, function, frozenset(hints), test, url.path, None)]
