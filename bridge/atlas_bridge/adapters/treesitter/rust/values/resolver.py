"""The strings a Rust expression can hold: literals, format!, concatenation, `join`, lets and consts."""

from ...kit import StringTemplate, ValueResolver
from ..blocks import Blocks
from ..names import ItemPath
from ..syntax import RustSyntax
from .concat import Concatenation
from .format import FormatMacro
from .pieces import UrlPiece
from .value import Value, ValueScope


class RustValues(ValueResolver):
    """resolve(node, ValueScope) -> [Value]. Depth (the kit's MAX_DEPTH) counts let and const hops; nesting
    counts every expression followed, far below Python's recursion limit."""

    HANDLERS = {
        'string_literal': '_literal',
        'raw_string_literal': '_literal',
        'macro_invocation': '_macro',
        'call_expression': '_call',
        'identifier': '_identifier',
        'scoped_identifier': '_constant',
        'field_expression': '_constant',
        'binary_expression': '_binary',
        **dict.fromkeys(Blocks.BRANCHING, '_branches'),
    }
    MAX_NESTING = 100  # expressions followed before giving up
    FORMAT_MACROS = frozenset({'format', 'format_args'})
    # Calls that build a value from their one argument unchanged: `String::from(x)`, `Cow::Borrowed(x)`.
    WRAPPERS = frozenset({'from', 'parse', 'from_static', 'Borrowed', 'Owned', 'try_from', 'from_str', 'Some', 'Ok'})

    def __init__(self, workspace):
        self._workspace = workspace
        self._concat = Concatenation(self)
        self._nesting = 0

    def values(self, file, node, join=False) -> list[Value]:
        return self.resolve(node, ValueScope(file, join))

    def resolve(self, node, scope, depth=0):
        if self._nesting >= self.MAX_NESTING:
            return []
        self._nesting += 1
        try:
            return super().resolve(RustSyntax.unwrap(node), scope, depth)
        finally:
            self._nesting -= 1

    def unknown(self, node, scope):
        return []

    def _literal(self, node, scope, depth):
        return [Value(StringTemplate.of(node), node, [])]

    def _macro(self, node, scope, depth):
        if RustSyntax.text(node.child_by_field_name('macro')).split('::')[-1] not in self.FORMAT_MACROS:
            return []
        v = FormatMacro.read(scope.file, node, scope.join)
        return [v] if v else []

    def _identifier(self, node, scope, depth):
        value = self._workspace.binding(scope.file, node)
        if value is not None:
            return self.resolve(value, scope, depth + 1)
        return self._constant(node, scope, depth)

    def _constant(self, node, scope, depth):
        hit = self._workspace.const_value(scope.file, node)
        if hit is None:
            return []
        return self.resolve(hit[1], scope.moved(hit[0]), depth + 1)

    def _binary(self, node, scope, depth):
        return self._concat.resolve(node, scope, depth) if RustSyntax.is_concat(node) else []

    def _branches(self, node, scope, depth):
        out = []
        for leaf in Blocks.leaves(node):
            out += self.resolve(leaf, scope, depth)
        return out

    def _call(self, node, scope, depth):
        args = RustSyntax.args(node)
        fn = RustSyntax.method(node)
        if fn is not None:
            return self._method_call(node, fn, args, scope, depth)
        segs = ItemPath.segments(node.child_by_field_name('function'))
        if segs and segs[-1] in self.WRAPPERS and len(args) == 1:
            return self.resolve(args[0], scope, depth)
        return []

    def _method_call(self, node, fn, args, scope, depth):
        name = RustSyntax.text(fn.child_by_field_name('field'))
        recv = fn.child_by_field_name('value')
        if name in UrlPiece.CONVERSIONS:
            return self.resolve(recv, scope, depth)
        if name == 'join' and len(args) == 1:
            return self._join(node, recv, args[0], scope, depth)
        return []

    def _join(self, node, recv, arg, scope, depth):
        """`base.join(rel)`: a relative path replaces the base's last segment, as Url::join does."""
        rel = self.resolve(arg, scope.joined(), depth)
        if not rel:
            return []
        value, _, hints = rel[0]
        hints = hints + [RustSyntax.text(recv)]
        if not UrlPiece.path_like(value):
            base = self.resolve(recv, scope.joined(False), depth)
            if base:
                bv = base[0].text
                value = bv[: bv.rfind('/') + 1] + value if '/' in bv else bv + '/' + value
                hints += base[0].hints
            else:
                value = '/' + value
        return [Value(value, node, hints)]
