"""The procedures of a tRPC router, nested routers included, with the dotted path each is called by."""

from typing import NamedTuple

from ..syntax.nodes import JsSyntax
from .names import TrpcNames


class Procedure(NamedTuple):
    """One procedure: its dotted path ('notes.create'), the HTTP method it is served with, and where its key is."""

    path: str
    method: str
    source: object  # the SourceFile its key is written in
    line: int
    handler: str  # '<router>.<key>'


class RouterTree:
    """Reads `router({ key: procedure | router | { ... } })`. A procedure is a builder chain ending in `.query(...)`
    or `.mutation(...)`; a router is a call of a router factory (TrpcNames.is_router) or, as tRPC v11 allows, a plain
    object literal of more keys. Values written elsewhere are followed through names and imports. A value that is
    neither adds nothing."""

    MAX_DEPTH = 8  # routers nested in routers
    KEYS = frozenset({'property_identifier', 'string'})

    def procedures(self, location, prefix='', depth=0) -> list[Procedure]:
        """The procedures of the router call (or plain object) at `location`, their paths behind `prefix`."""
        node = JsSyntax.unwrap(location.node) if location is not None else None
        if node is None or depth > self.MAX_DEPTH:
            return []
        if node.type == 'call_expression':
            args = JsSyntax.args(node)
            location = location.module.objects.locate(args[0]) if args else None
            node = JsSyntax.unwrap(location.node) if location is not None else None
        if node is None or node.type != 'object':
            return []
        owner = self._name(node)
        out = []
        for key, value in self._members(node):
            name = JsSyntax.string(key) if key.type == 'string' else JsSyntax.text(key)
            out += self._value(location.module, key, value, f'{prefix}{name}', owner, depth)
        return out

    def _value(self, module, key, value, path, owner, depth):
        """The procedures one key of a router stands for: itself, or those of the router it holds."""
        found = module.objects.origin(value)
        node = JsSyntax.unwrap(found.node) if found is not None else None
        if node is None:
            return []
        verb = self._verb(node)
        if verb:
            handler = f'{owner}.{path.rsplit(".", 1)[-1]}' if owner else path
            return [Procedure(path, TrpcNames.PROCEDURES[verb], module.source, JsSyntax.line(key), handler)]
        if node.type == 'object' or TrpcNames.is_router(found):
            return self.procedures(found, path + '.', depth + 1)
        return []

    @staticmethod
    def _verb(node):
        """'query' or 'mutation' for a procedure builder chain ending in one, else ''."""
        if node.type != 'call_expression':
            return ''
        fn = JsSyntax.unwrap(node.child_by_field_name('function'))
        if fn is None or fn.type != 'member_expression':
            return ''
        name = JsSyntax.text(fn.child_by_field_name('property'))
        return name if name in TrpcNames.PROCEDURES else ''

    @classmethod
    def _members(cls, obj):
        """(key, value) of each member whose name is written: `key: value`, `key` (shorthand)."""
        for member in obj.named_children:
            if member.type == 'shorthand_property_identifier':
                yield member, member
            elif member.type == 'pair' and member.child_by_field_name('key').type in cls.KEYS:
                yield member.child_by_field_name('key'), member.child_by_field_name('value')

    @staticmethod
    def _name(obj):
        """The name the router made of this object is bound to (`export const notesRouter = router({...})`), or ''."""
        node = JsSyntax.outer_parent(obj)
        if node is not None and node.type == 'arguments':
            node = JsSyntax.outer_parent(node.parent)
        if node is not None and node.type == 'variable_declarator':
            return JsSyntax.text(node.child_by_field_name('name'))
        return ''
