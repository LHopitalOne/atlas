"""Dict literals and what a literal key reads from them: `CONFIG['topic']`, `make()['name']`, `OVERRIDES.get(k, k)`."""

from ..syntax import PythonSyntax
from ..values import Marker
from .objects import Field


class MappingEntries:
    """The dict literals an expression may be (a literal, a name bound to one, `settings.NAME`, what a function of this
    repository returns for the call, an entry of another one), and the entries a key reads from them. A key is read
    only when it is known as literal text; an entry is found only under a key written as literal text. `get(key,
    default)` reads the default only from a dict that cannot hold the key: every key literal, no `**` unpacking."""

    MAX_DEPTH = 8
    GET = 'get'

    def __init__(self, resolver, bound):
        self._resolver = resolver  # resolves keys to their texts
        self._bound = bound  # BoundValues
        self._handlers = {
            'dictionary': lambda node, scope, depth: [Field(node, scope)],
            'parenthesized_expression': self._inner,
            'identifier': self._name,
            'attribute': self._name,
            'call': self._returned,
            'subscript': self._entry_dicts,
        }

    def dicts(self, node, scope, depth=0) -> list[Field]:
        handler = self._handlers.get(node.type) if node is not None and depth <= self.MAX_DEPTH else None
        return handler(node, scope, depth) if handler is not None else []

    def subscript(self, node, scope, depth=0) -> list[Field]:
        """The entries `mapping[key]` reads, with a key known as literal text."""
        keys = self.keys(node.child_by_field_name('subscript'), scope)
        if not keys:
            return []
        out = []
        for d in self.dicts(node.child_by_field_name('value'), scope, depth + 1):
            out += [Field(value, d.scope) for key, value in self._pairs(d) if key is not None and key & keys]
        return out

    def get(self, call, scope) -> list[Field] | None:
        """What `mapping.get(key[, default])` reads, or None when the receiver is not a dict literal."""
        fn = call.child_by_field_name('function')
        if fn.type != 'attribute' or PythonSyntax.text(fn.child_by_field_name('attribute')) != self.GET:
            return None
        pos, _ = PythonSyntax.call_args(call)
        found = self.dicts(fn.child_by_field_name('object'), scope) if 1 <= len(pos) <= 2 else []
        if not found:
            return None
        keys = self.keys(pos[0], scope)
        default = [Field(pos[1], scope)] if len(pos) == 2 else []
        out = []
        for d in found:
            pairs = self._pairs(d)
            hits = [Field(value, d.scope) for key, value in pairs if keys and key is not None and key & keys]
            closed = all(key is not None for key, _ in pairs)
            out += hits or (default if closed and (keys or not pairs) else [])
        return out

    def keys(self, node, scope) -> frozenset:
        """The texts a key may be, when every value it may hold is literal text; else empty."""
        values = self._resolver.resolve(node, scope) if node is not None else []
        if not values or not all(v.is_literal and not Marker.is_unresolved(v.text) for v in values):
            return frozenset()
        return frozenset(v.text for v in values)

    def _pairs(self, d):
        """[(key texts or None, value node)] of a dict literal; a `**` unpacking is an entry with unknown keys."""
        out = []
        for item in d.node.named_children:
            if item.type == 'pair':
                out.append(
                    (self.keys(item.child_by_field_name('key'), d.scope) or None, item.child_by_field_name('value'))
                )
            elif item.type == 'dictionary_splat':
                out.append((None, None))
        return out

    def _inner(self, node, scope, depth):
        return self.dicts(node.named_children[0], scope, depth + 1) if node.named_children else []

    def _name(self, node, scope, depth):
        return [d for f in self._bound.of(node, scope) for d in self.dicts(f.node, f.scope, depth + 1)]

    def _returned(self, call, scope, depth):
        """The dicts a function of this repository returns, read for this call."""
        found = self._bound.called(call, scope)
        if found is None:
            return []
        func, inner = found
        out = []
        for r in PythonSyntax.body_nodes(func.child_by_field_name('body')):
            if r.type == 'return_statement' and r.named_children:
                out += self.dicts(r.named_children[0], inner, depth + 1)
        return out

    def _entry_dicts(self, node, scope, depth):
        return [d for f in self.subscript(node, scope, depth) for d in self.dicts(f.node, f.scope, depth + 1)]
