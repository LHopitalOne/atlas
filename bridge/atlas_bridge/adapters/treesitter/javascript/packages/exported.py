"""What the functions a workspace package exports send: requests waiting for the arguments of their callers."""

from dataclasses import replace

from ..calls.composite import RequestCalls
from ..calls.forwarding import OpenRequest
from ..generated.requests import GeneratedRequests
from ..syntax.functions import Functions
from ..syntax.nodes import JsSyntax
from ..syntax.params import Params


class UnsettledRequests(RequestCalls):
    """The request idioms of RequestCalls, read from a file and handed back as they are: requests with their full
    paths (the client's base in front), and requests still open on their function's parameters."""

    def found(self):
        clients = self._clients.build()
        pending, opens = [(p, p.full_path(clients)) for p in self._pending], list(self._opens)
        self.start()
        return pending, opens


class PackageFunctions:
    """Reads the files of a WorkspacePackage where the names an application imports are defined, and turns every
    request of such a function into an OpenRequest named by the import (`@acme/sdk`): a request whose path is
    already known is one with nothing left to fill in. A request of another function, or of a class method, is
    left out. The parameters of the function are bound at its callers, whatever kind of request it holds."""

    def __init__(self, package):
        self._package = package
        self._read = {}  # module path -> (closed [(PendingRequest, full path)], [OpenRequest])

    def opens(self, specifier, subpath, names) -> list[OpenRequest]:
        out = []
        for name in sorted(names):
            found = self._package.definition(subpath, name)
            if found is not None:
                out += self._sent(specifier, name, *found)
        return out

    def _sent(self, specifier, name, module, node, defined):
        closed, opened = self._requests(module)
        first, last = node.start_point[0] + 1, node.end_point[0] + 1
        fn = JsSyntax.unwrap(node)
        params = Params.of(fn) if fn.type in Functions.FUNCTIONS else ()  # what a caller's arguments bind
        out = [
            OpenRequest(specifier, name, '', False, params, path, p.method, '', p.hints)
            for p, path in closed
            if p.function == defined and first <= p.line <= last and path
        ]
        out += [
            replace(o, path=specifier, function=name)
            for o in opened
            if o.function == defined and not o.method_of_class and not o.owner
        ]
        return out

    def _requests(self, module):
        if module.path not in self._read:
            workspace = self._package.workspace
            closed, opened = GeneratedRequests.read(workspace, module)
            plain = UnsettledRequests(workspace)
            plain.read(module)
            more, more_opened = plain.found()
            self._read[module.path] = ([(p, p.path) for p in closed] + more, opened + more_opened)
        return self._read[module.path]
