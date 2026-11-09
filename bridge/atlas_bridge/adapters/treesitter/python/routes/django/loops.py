"""Module-level `for` loops over literal strings: the texts a URLconf loop gives its variable."""

from ...scope import Scope
from ...syntax import PythonSyntax
from ...values import Marker, PythonValueResolver


class LoopValues:
    """`for app in ['a', 'b']:`, `for app in APPS:` or `for app in settings.APPS:` with APPS bound to a list, tuple or
    set literal: one {variable: text} per string literal in it (at most MAX_VALUES). Anything else gives nothing."""

    MAX_VALUES = 16
    SEQUENCES = frozenset({'list', 'tuple', 'set'})

    def __init__(self, workspace, values):
        self._workspace = workspace
        self._values = values

    def values(self, source, loop):
        """[{variable: text}] of a `for` statement, or [] when its variable or iterable is not plain."""
        left, right = loop.child_by_field_name('left'), loop.child_by_field_name('right')
        if left is None or left.type != 'identifier' or right is None:
            return []
        found = self._sequence(source, right)
        if found is None:
            return []
        where, sequence = found
        name, out = PythonSyntax.text(left), []
        for item in sequence.named_children:
            text = self._values.string(item, Scope.module(where)).text if item.type == 'string' else None
            if text is not None and not Marker.names(text) and '{' not in text:
                out.append({name: text})
        return out[: self.MAX_VALUES]

    def _sequence(self, source, node):
        """(file, literal) of the sequence an iterable is or names, or None."""
        if node.type in self.SEQUENCES:
            return source, node
        found = None
        owner = node.child_by_field_name('object') if node.type == 'attribute' else None
        if owner is not None and PythonSyntax.text(owner) == PythonValueResolver.SETTINGS:
            found = self._workspace.settings.value(PythonSyntax.text(node.child_by_field_name('attribute')))
        elif node.type in ('identifier', 'attribute'):
            symbol = self._workspace.names.value(source, node)
            found = (symbol.source, symbol.node) if symbol is not None else None
        return found if found is not None and found[1] is not None and found[1].type in self.SEQUENCES else None


class BoundText:
    """The text of a name or string read with some names bound to texts (a loop's variable, a builder's parameters):
    `app` and `f'{app}.urls'` with {app: 'billing'} give 'billing' and 'billing.urls'. An interpolated name not
    bound is read as a constant; None when one does not resolve to a single literal."""

    INTERPOLATION = 'interpolation'
    DELIMITERS = frozenset({'string_start', 'string_end'})

    def __init__(self, values):
        self._values = values

    def text(self, scope, node, given):
        """The text of `node` in `scope` with `given` {name: text}, or None."""
        if node.type == 'identifier' and PythonSyntax.text(node) in given:
            return given[PythonSyntax.text(node)]
        if node.type == 'string' and any(c.type == self.INTERPOLATION for c in node.children):
            return self._formatted(scope, node, given)
        return self.literal(scope, node, given)

    def mentions(self, node, given):
        """Whether `node` is, or interpolates, a bound name."""
        if node.type == 'identifier':
            return PythonSyntax.text(node) in given
        return node.type == 'string' and any(
            c.type == self.INTERPOLATION and c.named_children and PythonSyntax.text(c.named_children[0]) in given
            for c in node.children
        )

    def literal(self, scope, node, given):
        """The one literal text a node resolves to, builder parameter markers filled from `given`; or None."""
        found = self._values.resolve(node, scope)
        v = found[0] if len(found) == 1 else None
        text = Marker.fill(v.text, given) if v is not None and v.is_known else None
        return text if text is not None and not Marker.is_unresolved(text) and '{' not in text else None

    def _formatted(self, scope, node, given):
        out = []
        for c in node.children:
            if c.type in self.DELIMITERS:
                continue
            if c.type != self.INTERPOLATION:
                out.append(PythonSyntax.text(c).replace('{{', '{').replace('}}', '}'))
                continue
            expr = c.named_children[0] if c.named_children else None
            text = self.text(scope, expr, given) if expr is not None else None
            if text is None:
                return None
            out.append(text)
        return ''.join(out)
