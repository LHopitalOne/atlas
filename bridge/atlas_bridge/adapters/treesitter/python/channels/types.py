"""Which library object an expression holds: read from the call that made it or the annotation that names it."""

from typing import NamedTuple

from ..scope import Scope
from ..syntax import PythonSyntax
from .qualified import QualifiedNames
from .table import ChannelTable, LibraryType


class Made(NamedTuple):
    """A library object an expression holds, and the call that made it (None when only an annotation says so)."""

    type: LibraryType
    call: object = None


class LibraryTypes:
    """The library objects (ChannelTable.TYPES) an expression may hold."""

    MAX_DEPTH = 4  # factory methods followed: connection.channel() on pika.BlockingConnection(...)
    NAMES = ('identifier', 'attribute')
    TYPE_VARIABLES = frozenset({'typing.TypeVar', 'typing_extensions.TypeVar'})
    BOUND = 'bound'

    def __init__(self, workspace, origins, table=ChannelTable):
        self._workspace = workspace
        self._origins = origins
        self._names = QualifiedNames(workspace)
        self._table = table

    def of(self, node, scope, depth=0) -> list[Made]:
        if depth > self.MAX_DEPTH:
            return []
        out = []
        for origin in self._origins.of(node, scope):
            if origin.is_call:
                out += self._made_by(origin.node, origin.scope, depth)
            else:
                out += self._annotated(origin.node, origin.scope, depth)
        return out

    def _made_by(self, call, scope, depth):
        """The types a call makes: a creator of the type, or a factory method of another library object."""
        fn = call.child_by_field_name('function')
        qualified = self._names.of(scope.source, fn)
        out = [Made(t, call) for t in self._table.TYPES if self.creates(qualified, t)]
        if out or fn.type != 'attribute':
            return out
        method = PythonSyntax.text(fn.child_by_field_name('attribute'))
        for made in self.of(fn.child_by_field_name('object'), scope, depth + 1):
            out += [Made(t, call) for t in self._table.TYPES if self._factory(t, made.type, method)]
        return out

    def creates(self, qualified, t: LibraryType) -> bool:
        return any(QualifiedNames.matches(qualified, t.library, c) for c in t.creators)

    @staticmethod
    def _factory(t, maker, method):
        return t.library == maker.library and (maker.name, method) in t.factories

    def _annotated(self, annotation, scope, depth=0):
        """The types an annotation names: `KafkaProducer`, `redis.Redis | None`, `Optional[Producer]`, or a type
        variable's constraints or bound (`T = TypeVar('T', Channel, BlockingChannel)`)."""
        out = []
        for n in PythonSyntax.walk(annotation, self.NAMES):
            if n.type == 'identifier' and n.parent is not None and n.parent.type == 'attribute':
                continue  # a part of a dotted name, read with the whole
            qualified = self._names.of(scope.source, n)
            out += [Made(t) for t in self._table.TYPES if self._names_type(qualified, t)]
            if not qualified and depth < self.MAX_DEPTH:
                out += self._constrained(n, scope, depth + 1)
        return out

    @staticmethod
    def _names_type(qualified, t):
        return any(QualifiedNames.matches(qualified, t.library, name) for name in (t.name, *t.classes))

    def _constrained(self, node, scope, depth):
        """The types a module-level type variable stands for: its constraints, or its bound."""
        found = self._workspace.names.value(scope.source, node)
        call = found.node if found is not None else None
        if call is None or call.type != 'call':
            return []
        where = Scope.module(found.source)
        if self._names.of(found.source, call.child_by_field_name('function')) not in self.TYPE_VARIABLES:
            return []
        pos, kw = PythonSyntax.call_args(call)
        bounds = pos[1:] + ([kw[self.BOUND]] if self.BOUND in kw else [])
        return [made for b in bounds for made in self._annotated(b, where, depth)]
