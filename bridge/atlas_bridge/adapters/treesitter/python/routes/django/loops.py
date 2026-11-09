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
