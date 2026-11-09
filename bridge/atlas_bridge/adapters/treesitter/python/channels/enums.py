"""Members of this repository's Enum classes, read as the values they are assigned: `Topic.EVENTS.value` is 'events'
after `class Topic(Enum): EVENTS = 'events'`."""

from ..scope import Scope
from ..syntax import PythonSyntax
from ..values import Marker
from .objects import Field
from .qualified import QualifiedNames


class EnumMembers:
    """The members an expression may be: `E.MEMBER`, `E(value)` (the member with that value), and names, parameters,
    dict entries and conditionals holding them. A member reads as its value through `.value`; a member of a StrEnum is
    its value as it is, since its str() and format() are the value. A `(str, Enum)` member is not read as it is: its
    str() is 'E.MEMBER', and since Python 3.11 so is its format() (f-strings), so the text it gives depends on how it
    is used. A class is an enum when a base is the enum module's or another enum of this repository."""

    LIBRARY = 'enum'
    BASES = ('Enum', 'IntEnum', 'StrEnum', 'Flag', 'IntFlag')
    STR_ENUM = 'StrEnum'  # the enum module's base whose members are their values wherever a string is made of them
    VALUE = 'value'
    MAX_DEPTH = 8
    MAX_BASES = 3  # enum classes followed up the bases

    def __init__(self, workspace, resolver, bound, mappings):
        self._workspace = workspace
        self._resolver = resolver
        self._bound = bound  # BoundValues
        self._mappings = mappings  # MappingEntries
        self._names = QualifiedNames(workspace)
        self._handlers = {
            'attribute': self._attribute,
            'call': self._lookup,
            'identifier': self._name,
            'subscript': self._entry,
            'parenthesized_expression': self._parts,
            'conditional_expression': self._parts,
        }

    def value(self, node, scope) -> list[Field]:
        """What an attribute node reads as when it is a member's value: `<member>.value`, or a StrEnum's member."""
        attr = PythonSyntax.text(node.child_by_field_name('attribute'))
        if attr == self.VALUE:
            return self.of(node.child_by_field_name('object'), scope)
        found = self._enum(scope.source, node.child_by_field_name('object'))
        if found is None or not self._is_str(*found):
            return []
        return self._member(found, attr)

    def of(self, node, scope, depth=0) -> list[Field]:
        """The value expressions of the members `node` may be."""
        handler = self._handlers.get(node.type) if node is not None and depth <= self.MAX_DEPTH else None
        return handler(node, scope, depth) if handler is not None else []

    def _attribute(self, node, scope, depth):
        found = self._enum(scope.source, node.child_by_field_name('object'))
        if found is not None:
            return self._member(found, PythonSyntax.text(node.child_by_field_name('attribute')))
        return self._name(node, scope, depth)

    def _member(self, found, name):
        source, cls = found
        value = self._workspace.attributes.own(source, cls).get(name)
        return [Field(value, Scope(source, None, cls))] if value is not None else []

    def _lookup(self, call, scope, depth):
        """`E(value)`: the member whose value is the literal the call passes."""
        found = self._enum(scope.source, call.child_by_field_name('function'))
        pos, _ = PythonSyntax.call_args(call)
        if found is None or len(pos) != 1:
            return []
        wanted = self._texts(pos[0], scope)
        source, cls = found
        member_scope = Scope(source, None, cls)
        members = self._workspace.attributes.own(source, cls).values()
        return [Field(v, member_scope) for v in members if wanted & self._texts(v, member_scope)]

    def _texts(self, node, scope):
        values = self._resolver.settled(node, scope)
        return {v.text for v in values if v.is_literal and not Marker.is_unresolved(v.text)}

    def _name(self, node, scope, depth):
        return [m for f in self._bound.of(node, scope) for m in self.of(f.node, f.scope, depth + 1)]

    def _entry(self, node, scope, depth):
        return [m for f in self._mappings.subscript(node, scope) for m in self.of(f.node, f.scope, depth + 1)]

    def _parts(self, node, scope, depth):
        kids = node.named_children
        parts = kids[:1] if node.type == 'parenthesized_expression' else kids[:1] + kids[2:3]
        return [m for part in parts for m in self.of(part, scope, depth + 1)]

    def _enum(self, source, node, depth=0):
        """(source, class) when `node` names an Enum class of this repository, else None."""
        if node is None or node.type not in ('identifier', 'attribute') or depth > self.MAX_BASES:
            return None
        found = self._workspace.names.expression(source, node)
        if found is None or not found.is_class:
            return None
        for base in self._bases(found.node):
            qualified = self._names.of(found.source, base)
            if any(QualifiedNames.matches(qualified, self.LIBRARY, b) for b in self.BASES):
                return found.source, found.node
            if self._enum(found.source, base, depth + 1) is not None:
                return found.source, found.node
        return None

    def _is_str(self, source, cls, depth=0):
        """Whether the members of an enum class are their values as strings: a base is the enum module's StrEnum, here
        or up the bases."""
        for base in self._bases(cls):
            if QualifiedNames.matches(self._names.of(source, base), self.LIBRARY, self.STR_ENUM):
                return True
            parent = self._enum(source, base)
            if parent is not None and depth < self.MAX_BASES and self._is_str(*parent, depth + 1):
                return True
        return False

    @staticmethod
    def _bases(cls):
        bases = cls.child_by_field_name('superclasses')
        return [b for b in bases.named_children if b.type in ('identifier', 'attribute')] if bases is not None else []
