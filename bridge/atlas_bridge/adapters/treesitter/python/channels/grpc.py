"""gRPC with grpcio's generated code: servicers registered with `add_<Service>Servicer_to_server` serve
'/<Service>/<Method>'; `<Service>Stub(channel)` objects call it."""

import dataclasses
import re

from .....core.http import Extraction, Protocol
from ...kit import CallCollector, RouteCollector
from ..scope import Scope
from ..syntax import PythonSyntax
from .origins import Origins
from .qualified import QualifiedNames


class GrpcNames:
    """The names grpcio's protoc plugin generates in a `*_pb2_grpc` module, and the method a channel carries."""

    REGISTER = re.compile(r'^add_(\w+)Servicer_to_server$')  # registers a servicer; group 1 is the service
    STUB = re.compile(r'(?:^|\.)\w+_pb2_grpc\.(\w+)Stub$')  # a stub class; group 1 is the service
    METHOD = 'CALL'  # the operation of every gRPC route and call
    FRAMEWORK = 'grpc'

    @staticmethod
    def path(service, method):
        """The channel: '/<Service>/<Method>', without the proto package a servicer does not name."""
        return f'/{service}/{method}'


class GrpcServicers(RouteCollector):
    """`add_<Service>Servicer_to_server(servicer, server)`: each public method of the servicer's class (an instance
    made in this repository) is a route '/<Service>/<Method>'."""

    QUERY = '(call) @call'
    MENTION = b'Servicer_to_server'

    def __init__(self, workspace):
        super().__init__(workspace)
        self._origins = Origins(workspace)

    def collect(self) -> Extraction:
        routes = []
        for source in self.workspace.sources:
            for call in source.captures(self.QUERY).get('call', ()) if source.mentions(self.MENTION) else ():
                registers = GrpcNames.REGISTER.match(PythonSyntax.callee(call))
                if registers is None:
                    continue
                service = registers.group(1)
                pos, kw = PythonSyntax.call_args(call)
                servicer = pos[0] if pos else kw.get('servicer')
                for cls_source, cls in self._classes(servicer, Scope.at(source, call)):
                    routes += self._methods(cls_source, cls, service)
        return Extraction(routes=routes)

    def _classes(self, node, scope):
        out = []
        for origin in self._origins.of(node, scope):
            target = origin.node.child_by_field_name('function') if origin.is_call else origin.node
            found = self.workspace.names.expression(origin.scope.source, target) if target is not None else None
            if found is not None and found.is_class and found.node not in [c for _, c in out]:
                out.append((found.source, found.node))
        return out

    def _methods(self, source, cls, service):
        out = []
        for st in cls.child_by_field_name('body').named_children:
            func = st.child_by_field_name('definition') if st.type == 'decorated_definition' else st
            if func is None or func.type != 'function_definition' or PythonSyntax.name(func).startswith('_'):
                continue
            method = PythonSyntax.name(func)
            path = GrpcNames.path(service, method)
            handler = f'{PythonSyntax.name(cls)}.{method}'
            route = self.route(source, PythonSyntax.line(func), path, {GrpcNames.METHOD}, handler)
            out.append(dataclasses.replace(route, framework=GrpcNames.FRAMEWORK, protocol=Protocol.GRPC))
        return out


class GrpcStubs(CallCollector):
    """`stub.<Method>(request)` (or `.future(...)`, `.with_call(...)`) on an object made by `<Service>Stub(channel)`
    of a `*_pb2_grpc` module: a call of '/<Service>/<Method>'."""

    QUERY = '(call function: (attribute) @fn) @call'
    WRAPPERS = frozenset({'future', 'with_call'})  # the other ways to invoke a unary method

    def __init__(self, workspace):
        super().__init__(workspace)
        self._origins = Origins(workspace)
        self._names = QualifiedNames(workspace)

    def collect(self) -> Extraction:
        calls = []
        for source in self.workspace.sources:
            for call in source.captures(self.QUERY).get('call', ()) if source.mentions(b'Stub') else ():
                calls += self._call(source, call)
        return Extraction(calls=calls)

    def _call(self, source, call):
        fn = call.child_by_field_name('function')
        if PythonSyntax.text(fn.child_by_field_name('attribute')) in self.WRAPPERS:
            fn = fn.child_by_field_name('object')
        if fn.type != 'attribute':
            return []
        method = PythonSyntax.text(fn.child_by_field_name('attribute'))
        if not method[:1].isupper():
            return []  # generated stub attributes keep the proto's method names, written in CamelCase
        scope = Scope.at(source, call)
        out = []
        for service in self._services(fn.child_by_field_name('object'), scope):
            path = GrpcNames.path(service, method)
            test = self.workspace.is_test(source, call)
            line, function = PythonSyntax.line(call), scope.qualified
            out.append(self.call(source, line, path, GrpcNames.METHOD, function, test=test, protocol=Protocol.GRPC))
        return out

    def _services(self, receiver, scope):
        found = []
        for origin in self._origins.of(receiver, scope):
            if origin.is_call:
                qualified = self._names.of(origin.scope.source, origin.node.child_by_field_name('function'))
                m = GrpcNames.STUB.search(qualified)
                if m and m.group(1) not in found:
                    found.append(m.group(1))
        return found
