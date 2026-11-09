"""Reading a channel out of a call's arguments, in the shape a table row says it is written."""

import re

from ..scope import Scope
from ..syntax import PythonSyntax
from ..values import Marker, UrlShape
from .qualified import QualifiedNames
from .table import Argument, ChannelTable, Shape


class ChannelArguments:
    """The channel paths one argument of a call stands for: '/orders.created' for a topic, '/41210' for a port, the
    URL's path for a URL, the name a library object carries (`Topic('orders')`, ChannelTable.WRAPPERS). Only values
    fully known as literals count: a channel the code builds from what it cannot see is left out rather than guessed."""

    NAME = re.compile(r'^[^\s/{}]+$')  # a whole topic, queue or channel name: no blanks, slashes or placeholders
    PORT = re.compile(r'^[1-9]\d{0,4}$')  # a fixed port; 0 asks the system for any free one
    GLOB = re.compile(r'[*?]+')  # a run of glob wildcards in a subscription pattern
    SEQUENCES = ('list', 'tuple', 'set')
    ANY_PATH = '/{*path}'
    MAX_WRAPS = 3  # library objects followed inside one another: Partition(Topic(name), 0)

    def __init__(self, workspace, values, table=ChannelTable):
        self._workspace = workspace
        self._values = values  # ChannelValues
        self._table = table
        self._qualified = QualifiedNames(workspace)
        self._shapes = {
            Shape.NAME: self._names,
            Shape.NAMES: self._sequence,
            Shape.PATTERNS: self._patterns,
            Shape.ADDRESS: self._address,
            Shape.PORT: self._port,
            Shape.URL: self._url,
            Shape.OBJECT: self._object,
            Shape.OBJECTS: self._objects,
        }

    @staticmethod
    def nodes(argument: Argument, call) -> list:
        """The argument nodes a row's Argument names in a call (several for ALL)."""
        pos, kw = PythonSyntax.call_args(call)
        pos = [p for p in pos if p.type not in ('list_splat', 'dictionary_splat')]
        if argument.position == Argument.ALL:
            return pos
        if argument.position == Argument.LAST:
            return pos[-1:]
        if isinstance(argument.position, int) and len(pos) > argument.position:
            return [pos[argument.position]]
        found = kw.get(argument.keyword) if argument.keyword else None
        return [found] if found is not None else []

    def paths(self, argument: Argument, call, scope) -> list[str]:
        if argument.shape == Shape.ANY_PATH:
            return [self.ANY_PATH]
        read = self._shapes[argument.shape]
        found = [p for node in self.nodes(argument, call) for p in read(node, scope)]
        return list(dict.fromkeys(found))

    def literals(self, node, scope) -> list[str]:
        """The literal texts a value may have, its parameters settled at the function's call sites."""
        values = self._values.settled(node, scope, limit=self._values.MAX_CHANNELS)
        return [v.text for v in values if v.is_literal and not Marker.is_unresolved(v.text)]

    def _names(self, node, scope):
        return ['/' + t for t in self.literals(node, scope) if self.NAME.match(t)]

    def _sequence(self, node, scope):
        items = node.named_children if node.type in self.SEQUENCES else [node]
        return [p for item in items for p in self._names(item, scope)]

    def _patterns(self, node, scope):
        return [self.GLOB.sub('{pattern}', p) for p in self._sequence(node, scope)]

    def _object(self, node, scope, depth=0):
        """The names a library object carries, read from the calls that made it (Origins)."""
        out = []
        for origin in self._values.origins.of(node, scope) if depth <= self.MAX_WRAPS else ():
            if not origin.is_call:
                continue
            qualified = self._qualified.of(origin.scope.source, origin.node.child_by_field_name('function'))
            for wrapper in self._table.WRAPPERS:
                if not QualifiedNames.matches(qualified, wrapper.library, wrapper.name):
                    continue
                for arg in self.nodes(wrapper.argument, origin.node):
                    inner = wrapper.argument.shape == Shape.OBJECT
                    out += self._object(arg, origin.scope, depth + 1) if inner else self._names(arg, origin.scope)
        return out

    def _objects(self, node, scope):
        node, scope = self._bound(node, scope)
        items = node.named_children if node.type in self.SEQUENCES else [node]
        return [p for item in items for p in self._object(item, scope)]

    def _port(self, node, scope):
        return ['/' + t for t in self.literals(node, scope) if self.PORT.match(t)]

    def _url(self, node, scope):
        out = []
        for text in self.literals(node, scope):
            path = UrlShape.split(text).path
            if path is not None and '{' not in path:
                out.append(path)
        return out

    def _address(self, node, scope):
        """A (host, port) tuple, written in the call or bound to a name: its port."""
        node, scope = self._bound(node, scope)
        if node.type != 'tuple' or len(node.named_children) != 2:
            return []
        return self._port(node.named_children[1], scope)

    def _bound(self, node, scope):
        """The value a local or module-level name is bound to, else the node itself."""
        if node.type == 'identifier' and scope.func is not None:
            prior = self._workspace.locals.before(scope.source, scope.func, PythonSyntax.text(node), node.start_byte)
            if prior:
                return prior[-1].value, scope
        found = self._workspace.names.value(scope.source, node) if node.type in ('identifier', 'attribute') else None
        return (found.node, Scope.module(found.source)) if found is not None else (node, scope)
