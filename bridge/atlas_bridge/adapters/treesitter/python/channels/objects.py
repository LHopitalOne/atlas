"""The fields of this repository's objects: `settings.port` where `settings` is a `Settings(port=...)`, an instance of
a class whose body sets `port = ...`, or of a dataclass whose `port` field has a default."""

from typing import NamedTuple

from ..scope import Scope
from ..syntax import PythonSyntax


class Field(NamedTuple):
    """An expression a field may hold, and where to read it."""

    node: object
    scope: Scope


class ObjectFields:
    """What `obj.attr` holds, from the classes `obj` is an instance of (Origins: calls of a class of this repository,
    or annotations naming one): the call's keyword argument, else the class body's value, else what a method assigns
    to `self.attr`. A dataclass `field(default=...)` or `field(default_factory=lambda: ...)` reads as its default."""

    DEFAULTS = frozenset({'field', 'Field'})  # dataclasses.field, pydantic.Field
    DEFAULT_KEYWORDS = ('default', 'default_factory')

    def __init__(self, workspace, origins):
        self._workspace = workspace
        self._origins = origins

    def of(self, node, scope) -> list[Field]:
        """The expressions `node.attr` (an attribute node) may hold."""
        attr = PythonSyntax.text(node.child_by_field_name('attribute'))
        out = []
        for origin in self._origins.of(node.child_by_field_name('object'), scope):
            target = origin.node.child_by_field_name('function') if origin.is_call else origin.node
            for source, cls in self._classes(target, origin.scope):
                out += self._field(source, cls, attr, origin.node if origin.is_call else None, origin.scope)
        return out

    def _classes(self, node, scope):
        """[(source, class node)] a callee or annotation names in this repository."""
        out = []
        for n in PythonSyntax.walk(node, ('identifier', 'attribute')) if node is not None else ():
            if n.parent is not None and n.parent.type == 'attribute' and n.parent != node:
                continue
            found = self._workspace.names.expression(scope.source, n)
            if found is not None and found.is_class:
                out.append((found.source, found.node))
        return out

    def _field(self, source, cls, attr, call, scope):
        if call is not None:
            _, kw = PythonSyntax.call_args(call)
            if attr in kw:
                return [Field(kw[attr], scope)]
        value = self._workspace.attributes.own(source, cls).get(attr)
        if value is not None:
            return [self._default(value, Scope(source, None, cls))]
        out = []
        for value, _ in self._origins.assignments(cls, attr):
            if value is not None:
                out.append(Field(value, Scope.at(source, value)))
        return out

    def _default(self, value, scope):
        """A class body value; `field(default=x)` and `field(default_factory=lambda: x)` read as x."""
        if value.type != 'call' or PythonSyntax.callee(value) not in self.DEFAULTS:
            return Field(value, scope)
        pos, kw = PythonSyntax.call_args(value)
        for key in self.DEFAULT_KEYWORDS:
            found = kw.get(key)
            if found is not None and found.type == 'lambda':
                return Field(found.child_by_field_name('body'), scope)
            if found is not None and key == 'default':
                return Field(found, scope)
        return Field(pos[0], scope) if pos and PythonSyntax.callee(value) == 'Field' else Field(value, scope)
