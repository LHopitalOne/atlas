"""Socket.IO in Python (python-socketio and Flask-SocketIO): the events a service emits and handles, as websocket
channels '<namespace>:<event>' ('/quiz:join'; '/:chat' in the main namespace), the same channels the JavaScript
reader gives socket.io and socket.io-client."""

import dataclasses

from .....core.http import Extraction, Protocol
from ...kit import CallCollector, RouteCollector
from ..scope import Scope
from ..syntax import PythonSyntax
from .arguments import ChannelArguments
from .qualified import QualifiedNames
from .table import LibraryType
from .types import LibraryTypes
from .values import ChannelValues


class SocketIoApi:
    """What the libraries name: the objects that emit and handle events, the namespace classes, and the events
    Socket.IO raises itself (no application emits them)."""

    LIBRARY = 'socketio'
    TYPES = (
        LibraryType('socketio', 'Client', ('Client', 'AsyncClient')),
        LibraryType('socketio', 'Server', ('Server', 'AsyncServer')),
        LibraryType('flask_socketio', 'SocketIO', ('SocketIO',)),
    )
    # class-based namespaces: methods named on_<event> handle the event, self.emit(event) sends in the namespace
    NAMESPACE_CLASSES = ('Namespace', 'AsyncNamespace', 'ClientNamespace', 'AsyncClientNamespace')
    HANDLER = 'on_'
    SENDS = frozenset({'emit', 'call'})  # (event, data, ..., namespace=)
    SEND_MESSAGE = 'send'  # send(data) emits the 'message' event
    MESSAGE = 'message'
    RECEIVE = 'on'  # @sio.on(event, namespace=) or sio.on(event, handler, namespace=)
    DECORATOR = 'event'  # @sio.event: the function's name is the event
    NAMESPACE = 'namespace'
    INIT = '__init__'
    MAIN = '/'
    RESERVED = frozenset({'connect', 'disconnect', 'connect_error'})
    METHOD = 'EMIT'
    FRAMEWORK = 'socket.io'

    @staticmethod
    def path(namespace, event):
        return f'/{namespace.strip("/")}:{event}'


class SocketIoEvents(RouteCollector, CallCollector):
    """Events of python-socketio clients and servers and of Flask-SocketIO, in both styles the libraries offer:
    a namespace class (`class Bot(socketio.AsyncClientNamespace)` with `on_<event>` methods and `self.emit`), and
    decorators and calls on a client or server object (`@sio.on('chat')`, `@sio.event`, `sio.emit('chat', data,
    namespace='/room')`). A namespace or event the code does not fix as a literal is left out."""

    MENTION = b'socketio'
    CLASSES = '(class_definition) @cls'
    CALLS = '(call function: (attribute)) @call'

    def __init__(self, workspace):
        super().__init__(workspace)
        values = ChannelValues(workspace)
        self._arguments = ChannelArguments(workspace, values)
        self._types = LibraryTypes(workspace, values.origins, SocketIoApi)
        self._names = QualifiedNames(workspace)

    def collect(self) -> Extraction:
        out = Extraction()
        for source in self.workspace.sources:
            if not source.mentions(self.MENTION):
                continue
            for cls in source.captures(self.CLASSES).get('cls', ()):
                if self._is_namespace_class(source, cls):
                    out.extend(self._namespace_class(source, cls))
            for call in source.captures(self.CALLS).get('call', ()):
                out.extend(self._object_call(source, call))
            out.routes += self._decorators(source)
        return out

    # class-based namespaces

    def _is_namespace_class(self, source, cls):
        bases = cls.child_by_field_name('superclasses')
        for base in bases.named_children if bases is not None else ():
            qualified = self._names.of(source, base)
            if any(QualifiedNames.matches(qualified, SocketIoApi.LIBRARY, n) for n in SocketIoApi.NAMESPACE_CLASSES):
                return True
        return False

    def _namespace_class(self, source, cls):
        out = Extraction()
        namespaces = self._class_namespaces(source, cls)
        for func in self._methods(cls):
            name = PythonSyntax.name(func)
            if name.startswith(SocketIoApi.HANDLER):
                out.routes += self._routes(source, func, namespaces, [name[len(SocketIoApi.HANDLER) :]])
        for call in PythonSyntax.walk(cls, ('call',)):
            fn = call.child_by_field_name('function')
            if fn.type == 'attribute' and PythonSyntax.is_self(fn.child_by_field_name('object')):
                out.calls += self._sends(source, call, namespaces)
        return out

    def _class_namespaces(self, source, cls):
        """The namespaces a namespace class serves: what its __init__ hands to the library's
        (`super().__init__('/quiz')`), else what the code that makes it passes (`Bot('/quiz')`)."""
        init = next((f for f in self._methods(cls) if PythonSyntax.name(f) == SocketIoApi.INIT), None)
        if init is not None:
            for call in PythonSyntax.walk(init, ('call',)):
                if PythonSyntax.callee(call) == SocketIoApi.INIT and 'super' in PythonSyntax.text(call):
                    return self._namespaces(call, Scope.at(source, call))
            return []
        unique = len([c for c in self.workspace.classes(PythonSyntax.name(cls)) if not c[0].test]) == 1
        found = []
        for other, call in self.workspace.callers.constructions_of(source, cls, unique):
            found += [n for n in self._namespaces(call, Scope.at(other, call)) if n not in found]
        return found

    @staticmethod
    def _methods(cls):
        """The class's own methods (not functions nested in them, nor methods of nested classes)."""
        around = PythonSyntax.FUNCTION + PythonSyntax.CLASS
        body = cls.child_by_field_name('body')
        return [f for f in PythonSyntax.walk(body, PythonSyntax.FUNCTION) if PythonSyntax.ancestor(f, around) == cls]

    # calls and decorators on client and server objects

    def _object_call(self, source, call):
        fn = call.child_by_field_name('function')
        method = PythonSyntax.text(fn.child_by_field_name('attribute'))
        if method not in SocketIoApi.SENDS | {SocketIoApi.SEND_MESSAGE, SocketIoApi.RECEIVE}:
            return Extraction()
        receiver = fn.child_by_field_name('object')
        scope = Scope.at(source, call)
        if PythonSyntax.is_self(receiver) or not self._types.of(receiver, scope):
            return Extraction()
        if method != SocketIoApi.RECEIVE:
            return Extraction(calls=self._sends(source, call, [SocketIoApi.MAIN]))
        handler = self._decorated(call)
        events = self._events(call, scope)
        return Extraction(routes=self._routes(source, handler or call, self._namespaces(call, scope), events))

    def _decorators(self, source):
        """`@sio.event` on a function: the function's name is an event of the main namespace."""
        out = []
        for node in PythonSyntax.walk(source.root, ('decorator',)):
            target = node.named_children[0] if node.named_children else None
            if target is None or target.type != 'attribute':
                continue
            if PythonSyntax.text(target.child_by_field_name('attribute')) != SocketIoApi.DECORATOR:
                continue
            if not self._types.of(target.child_by_field_name('object'), Scope.at(source, node)):
                continue
            func = node.parent.child_by_field_name('definition')
            if func is not None:
                out += self._routes(source, func, [SocketIoApi.MAIN], [PythonSyntax.name(func)])
        return out

    @staticmethod
    def _decorated(call):
        """The function a call decorates (`@sio.on('chat')`), or None."""
        parent = call.parent
        if parent is None or parent.type != 'decorator' or parent.parent is None:
            return None
        return parent.parent.child_by_field_name('definition')

    # reading events and namespaces

    def _sends(self, source, call, namespaces):
        """The calls of an emit, call or send: one per namespace and literal event."""
        scope = Scope.at(source, call)
        fn = call.child_by_field_name('function')
        if PythonSyntax.text(fn.child_by_field_name('attribute')) == SocketIoApi.SEND_MESSAGE:
            events = [SocketIoApi.MESSAGE]
        elif PythonSyntax.text(fn.child_by_field_name('attribute')) in SocketIoApi.SENDS:
            events = self._events(call, scope)
        else:
            return []
        _, kw = PythonSyntax.call_args(call)
        if SocketIoApi.NAMESPACE in kw:
            namespaces = self._literals(kw[SocketIoApi.NAMESPACE], scope)
        test = self.workspace.is_test(source, call)
        line, function = PythonSyntax.line(call), scope.qualified
        return [
            self.call(
                source,
                line,
                SocketIoApi.path(n, e),
                SocketIoApi.METHOD,
                function,
                test=test,
                protocol=Protocol.WEBSOCKET,
            )
            for n in namespaces
            for e in events
        ]

    def _routes(self, source, at, namespaces, events):
        if self.workspace.is_test(source, at):
            return []  # a test that listens stands in for a peer
        handler = Scope.at(source, at).qualified if at.type not in PythonSyntax.FUNCTION else self._handler(at)
        out = []
        for namespace in namespaces:
            for event in events:
                if event in SocketIoApi.RESERVED:
                    continue
                route = self.route(
                    source, PythonSyntax.line(at), SocketIoApi.path(namespace, event), {SocketIoApi.METHOD}, handler
                )
                out.append(dataclasses.replace(route, framework=SocketIoApi.FRAMEWORK, protocol=Protocol.WEBSOCKET))
        return out

    @staticmethod
    def _handler(func):
        cls = PythonSyntax.ancestor(func, PythonSyntax.CLASS)
        name = PythonSyntax.name(func)
        return f'{PythonSyntax.name(cls)}.{name}' if cls is not None else name

    def _events(self, call, scope):
        pos, kw = PythonSyntax.call_args(call)
        node = pos[0] if pos else kw.get('event')
        return [e for e in self._literals(node, scope) if e not in SocketIoApi.RESERVED] if node is not None else []

    def _namespaces(self, call, scope):
        """The namespace a call names (its first argument for a namespace's __init__, else namespace=), the main one
        when it names none."""
        pos, kw = PythonSyntax.call_args(call)
        node = kw.get(SocketIoApi.NAMESPACE)
        if node is None and PythonSyntax.callee(call) != SocketIoApi.RECEIVE:
            node = pos[0] if pos else None
        if node is None or node.type == 'none':
            return [SocketIoApi.MAIN]
        return [n for n in self._literals(node, scope) if n.startswith('/')]

    def _literals(self, node, scope):
        return [t for t in self._arguments.literals(node, scope) if t and '{' not in t]
