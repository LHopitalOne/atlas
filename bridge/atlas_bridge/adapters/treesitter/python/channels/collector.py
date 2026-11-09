"""ChannelEndpoints: the sends and receives of the libraries in the channel table, as calls and routes."""

import dataclasses

from .....core.http import Extraction
from ...kit import CallCollector, RouteCollector
from ..scope import Scope
from ..syntax import PythonSyntax
from .arguments import ChannelArguments
from .qualified import QualifiedNames
from .table import ChannelTable, Endpoint, Role
from .types import LibraryTypes
from .values import ChannelValues


class ChannelEndpoints(RouteCollector, CallCollector):
    """Each call a table row describes: a function of the library module, a call that makes one of its objects, or
    a method of an object it made (read through LibraryTypes). Receives become routes, sends become calls; the channel
    is the row's argument (ChannelArguments). A call on an object nobody can trace to the library is left out."""

    DATAGRAM = b'SOCK_DGRAM'  # the socket type of UDP sockets

    def __init__(self, workspace, table=ChannelTable):
        super().__init__(workspace)
        values = ChannelValues(workspace)
        self._table = table
        self._types = LibraryTypes(workspace, values.origins, table)
        self._arguments = ChannelArguments(workspace, values)
        self._names = QualifiedNames(workspace)
        callees = ' '.join(f'"{n}"' for n in sorted(table.callees()))
        self._query = f"""
        (call function: [(identifier) @fn (attribute attribute: (identifier) @fn)] (#any-of? @fn {callees})) @call
        """

    def collect(self) -> Extraction:
        out = Extraction()
        for source in self.workspace.sources:
            for call in source.captures(self._query).get('call', ()):
                scope = Scope.at(source, call)
                for endpoint, made in self._endpoints(call, scope):
                    out.extend(self._emit(endpoint, made, call, scope))
        return out

    def _endpoints(self, call, scope):
        """(row, the call that made the receiver or None) for each row this call matches."""
        fn = call.child_by_field_name('function')
        callee = PythonSyntax.callee(call)
        qualified = self._names.of(scope.source, fn)
        received = None
        for e in self._table.ENDPOINTS:
            if e.kind == Endpoint.MODULE:
                if e.callee == callee and QualifiedNames.matches(qualified, e.library, e.callee):
                    yield e, None
            elif e.callee == Endpoint.NEW:
                if self._types.creates(qualified, self._table.type_named(e.library, e.kind)):
                    yield e, call
            elif e.callee == callee and fn.type == 'attribute':
                if received is None:
                    received = self._types.of(fn.child_by_field_name('object'), scope)
                made = next((m for m in received if (m.type.library, m.type.name) == (e.library, e.kind)), None)
                if made is not None:
                    yield e, made.call

    def _emit(self, endpoint, made, call, scope) -> Extraction:
        if not all(self._holds(argument, literal, call, scope) for argument, literal in endpoint.requires):
            return Extraction()
        protocol = endpoint.protocol
        if endpoint.datagram and made is not None and self.DATAGRAM in made.text:
            protocol = endpoint.datagram
        source, line = scope.source, PythonSyntax.line(call)
        test = self.workspace.is_test(source, call)
        out = Extraction()
        if test and endpoint.role == Role.RECEIVE:
            return out  # a test that listens stands in for a peer; it is no channel the service receives on
        for path in self._arguments.paths(endpoint.channel, call, scope):
            if endpoint.role == Role.RECEIVE:
                route = self.route(source, line, path, {endpoint.method}, scope.qualified)
                out.routes.append(dataclasses.replace(route, framework=endpoint.library, protocol=protocol))
            else:
                out.calls.append(
                    self.call(source, line, path, endpoint.method, scope.qualified, test=test, protocol=protocol)
                )
        return out

    def _holds(self, argument, literal, call, scope):
        """Whether the argument is written and can only be `literal`."""
        nodes = ChannelArguments.nodes(argument, call)
        texts = self._arguments.literals(nodes[0], scope) if nodes else []
        return bool(texts) and all(t == literal for t in texts)
