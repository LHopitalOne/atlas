"""The value of a channel expression: what UrlValues reads in one file, plus where channels are usually kept."""

from ..bindings.binding import ParamBinding
from ..syntax.members import Members
from ..syntax.nodes import JsSyntax
from ..values.resolver import UrlValues
from ..values.urls import UrlText
from .callers import Callers
from .enums import EnumMembers
from .properties import ParameterProperties


class ChannelValues(UrlValues):
    """UrlValues (literals, templates, `+`, `process.env.X ?? 'default'`, local consts and helpers) of one file, also
    following a name to where the channel is kept: a constant or config object another file of the repository
    exports, a TypeScript enum's member, `this.field` (a class field, an assignment, a constructor parameter property),
    a parameter (its default, or what its callers pass), `Number(...)` around a port. A value that depends on which
    caller it came from is only taken when every caller agrees; `candidates` gives one per caller instead."""

    HANDLERS = {**UrlValues.HANDLERS, 'shorthand_property_identifier': '_identifier'}
    CONVERSIONS = frozenset({'Number', 'parseInt', 'parseFloat', 'String'})

    def __init__(self, scopes, file):
        super().__init__(scopes)
        self._file = file
        self._callers = Callers(file)
        self._enums = EnumMembers(file)

    def candidates(self, node, hints) -> list[str]:
        """The literal values `node` holds: its value, or, for a parameter, each value its callers pass."""
        value = self.resolve(node, hints)
        if UrlText.literal(value):
            return [value]
        node = JsSyntax.unwrap(node)
        if node is None or node.type not in ('identifier', 'shorthand_property_identifier'):
            return []
        found = self._definitions(node)
        return list(dict.fromkeys(v for v in self._each(found, hints, 0) if UrlText.literal(v)))

    def objects(self, node, depth=0):
        """[(file, object literal)] an expression stands for: a literal, a const bound to one, an import of one, a
        property of one (`config.inventory`)."""
        node = JsSyntax.unwrap(node)
        if node is None or depth > self.MAX_DEPTH:
            return []
        if node.type == 'object':
            return [(self._file, node)]
        if node.type in ('identifier', 'shorthand_property_identifier'):
            value = self._scopes.lookup(node, JsSyntax.text(node))
            if value is not None:
                return self.objects(value, depth + 1)
            return [(f, o) for f, n in self._imported(node) for f, o in f.values.objects(n, depth + 1)]
        if node.type == 'call_expression' and JsSyntax.require(node):
            target = self._file.graph.file_for(self._file.path, JsSyntax.require(node))
            exported = target.exported('default') if target is not None else None
            return target.values.objects(exported, depth + 1) if exported is not None else []
        if node.type == 'member_expression':
            key = JsSyntax.text(node.child_by_field_name('property'))
            inner = self.objects(node.child_by_field_name('object'), depth + 1)
            return [(f, o) for f, p in self._props(inner, key) for f, o in f.values.objects(p, depth + 1)]
        return []

    def _identifier(self, node, hints, depth):
        value = super()._identifier(node, hints, depth)
        if UrlText.literal(value) or depth >= self.MAX_DEPTH:
            return value
        found = self._first(self._definitions(node), hints, depth)
        return found if found is not None else value

    def _member(self, node, hints, depth):
        """`this.field`, or a key of an object literal (`config.port`, `settings.kafka.topic`)."""
        key = JsSyntax.text(node.child_by_field_name('property'))
        obj = JsSyntax.unwrap(node.child_by_field_name('object'))
        if obj is not None and obj.type == 'this':
            found = [(self._file, v) for v in Members.of_this(node, key)] + self._parameter_property(node, key)
        else:
            member = self._enums.member(obj, key)
            found = [member] if member is not None else self._props(self.objects(obj, depth + 1), key)
        value = self._first(found, hints, depth)
        return value if value is not None else super()._member(node, hints, depth)

    def _call(self, node, hints, depth):
        """`Number(port)` is its argument; a helper another file exports is what it returns."""
        fn, args = JsSyntax.unwrap(node.child_by_field_name('function')), JsSyntax.args(node)
        if fn is not None and fn.type == 'identifier':
            if JsSyntax.text(fn) in self.CONVERSIONS and args:
                return self.resolve(args[0], hints, depth)
            returned = [(f, self._returned(n)) for f, n in self._imported(fn) if n.type in self.FUNCTIONS]
            value = self._first([(f, r) for f, r in returned if r is not None], hints, depth)
            if value is not None:
                hints.add(JsSyntax.text(fn))
                return value
        return super()._call(node, hints, depth)

    def _definitions(self, node):
        """[(file, expression)] a name may hold when this file binds it to no value: an import, or a parameter (its
        default, and what callers pass)."""
        binding = self._scopes.binding(node, JsSyntax.text(node))
        if binding is None:
            return self._imported(node)
        if isinstance(binding, ParamBinding) and binding.node.type != 'variable_declarator':
            return self._callers.arguments(binding.node)
        return []

    def _imported(self, node):
        found = self._file.imported(node)
        return [found] if found is not None else []

    def _parameter_property(self, node, key):
        """The constructor parameter that declares `this.key` (`constructor(private url = WS_URL)`)."""
        param = ParameterProperties.of(node, key)
        return self._callers.arguments(param) if param is not None else []

    @staticmethod
    def _props(objects, key):
        found = ((f, JsSyntax.prop(o, key)) for f, o in objects)
        return [(f, p) for f, p in found if p is not None]

    def _each(self, found, hints, depth):
        for file, node in found:
            yield file.values.resolve(node, hints, depth + 1)

    def _first(self, found, hints, depth):
        """The one literal value the expressions agree on; None when there is none, or more than one."""
        values = {v for v in self._each(found, hints, depth) if UrlText.literal(v)}
        return values.pop() if len(values) == 1 else None
