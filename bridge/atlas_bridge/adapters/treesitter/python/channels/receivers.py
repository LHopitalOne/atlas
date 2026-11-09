"""Calls of a method on objects of its own class: `producer.produce(...)` where `producer = Wrapper(...)`."""

from ..scope import Scope
from ..syntax import PythonSyntax


class MethodCallers:
    """The calls `obj.method(...)` whose receiver comes from the method's class (Origins: a call of the class, or an
    annotation naming it). Calls by name alone reach a method only when no other definition shares its name
    (CallerIndex); these reach it whatever its name, because the receiver says which class it is."""

    NAMES = ('identifier', 'attribute')

    def __init__(self, workspace, origins):
        self._workspace = workspace
        self._origins = origins
        self._cache = {}  # (path, function start byte) -> [(source, call)]
        self._open = set()  # methods being read: a receiver traced back through the same method stops there

    def of(self, source, func, cls) -> list:
        """[(source, call node)] of the calls of `func`, a method of `cls`, on objects of that class."""
        key = (source.path, func.start_byte)
        if key in self._cache:
            return self._cache[key]
        if key in self._open:
            return []
        self._open.add(key)
        try:
            found = self._cache[key] = self._calls(source, func, cls)
        finally:
            self._open.discard(key)
        return found

    def _calls(self, source, func, cls):
        out = []
        for other, call in self._workspace.callers.calls_named(PythonSyntax.name(func)):
            fn = call.child_by_field_name('function')
            if fn.type != 'attribute' or PythonSyntax.is_self(fn.child_by_field_name('object')):
                continue
            if self._made_from(fn.child_by_field_name('object'), Scope.at(other, call), source, cls):
                out.append((other, call))
        return out

    def _made_from(self, receiver, scope, source, cls):
        """Whether an origin of the receiver is a call of `cls` or an annotation naming it."""
        for origin in self._origins.of(receiver, scope):
            target = origin.node.child_by_field_name('function') if origin.is_call else origin.node
            for n in PythonSyntax.walk(target, self.NAMES) if target is not None else ():
                if n.parent is not None and n.parent.type == 'attribute' and n != target:
                    continue  # a part of a dotted name, read with the whole
                found = self._workspace.names.expression(origin.scope.source, n)
                if found is not None and found.is_class and self._same(found, source, cls):
                    return True
        return False

    @staticmethod
    def _same(found, source, cls):
        return found.source.path == source.path and found.node.start_byte == cls.start_byte
