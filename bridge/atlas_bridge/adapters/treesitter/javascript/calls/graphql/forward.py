"""A GraphQL document handed to a helper as a parameter (`gql(ROOMS_QUERY, { city })`), followed to the calls that
give it."""

from dataclasses import dataclass

from ...syntax.functions import Functions
from ...syntax.nodes import JsSyntax
from ..forwarding import Forwarder
from .document import GraphqlDocument
from .text import DocumentText


@dataclass(frozen=True)
class OpenDocument:
    """A GraphQL request whose document is the parameter at `index` of a function, waiting for its callers. Plain
    data only, like forwarding.OpenRequest (whose caller lookup it shares)."""

    path: str  # the file of the function
    function: str
    owner: str  # the class of a method
    method_of_class: bool
    index: int
    hints: frozenset

    @classmethod
    def at(cls, module, fn, index, node, hints):
        """The open document of parameter `index` of `fn`, read at `node` (the request)."""
        _, owner = Functions.enclosing(node)
        kind = fn.type == 'method_definition'
        return cls(module.path, Functions.name(fn), owner, kind, index, frozenset(hints))


class DocumentForwarder(Forwarder):
    """Settles open documents at the calls of their functions, found as Forwarder finds them (a function by name in
    its file and the files that import it, a method through `this`). The argument a call gives is read as a document
    in the caller's file, following imports (a query constant of another module); an argument that is again a
    parameter opens the document one level up. `emit(module, call, operations, hints)` makes the calls."""

    def __init__(self, workspace, emit):
        super().__init__(workspace)
        self._emit = emit
        self._linker = workspace.linker()

    def settle(self, opens) -> list:
        found = super().settle(opens)
        self._linker.release()
        return found

    def _module(self, source):
        if source.path not in self._modules:
            self._modules[source.path] = self._workspace.module(source, self._linker)
        return self._modules[source.path]

    def _at(self, open_, module, call):
        args = JsSyntax.args(call)
        if open_.index >= len(args):
            return [], []
        arg = args[open_.index]
        hints = set(open_.hints) | {open_.function}
        operations = GraphqlDocument(DocumentText.of(module, arg) or '').operations()
        if operations:
            return self._emit(module, call, operations, hints), []
        param = DocumentText.parameter(module, arg)
        if param is None:
            return [], []
        return [], [OpenDocument.at(module, param[0], param[1], call, hints)]
