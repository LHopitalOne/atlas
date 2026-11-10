"""`base + "/x/" + &id`: string concatenation as a URL template."""

from ..syntax import RustSyntax
from .pieces import UrlPiece
from .value import Value


class Concatenation:
    """Known parts are kept, an unknown first part is the base, later unknown ones become {params}."""

    def __init__(self, resolver):
        self._resolver = resolver

    @staticmethod
    def operands(node):
        """`a + b + c` -> [a, b, c]. Folded iteratively: the sum nests to the left."""
        operands = []
        while RustSyntax.is_concat(node):
            operands.append(node.child_by_field_name('right'))
            node = RustSyntax.unwrap(node.child_by_field_name('left'))
        operands.append(node)
        operands.reverse()
        return operands

    def resolve(self, node, scope, depth):
        operands = self.operands(node)
        value, hints = None, []
        for i, part in enumerate(operands):
            found = self._resolver.resolve(part, scope.joined(scope.join or i > 0), depth)
            if found:
                v, _, more = found[0]
                if value is not None:
                    value, hints = value + v, hints + more
                elif i:  # what came before is unknown: the base
                    value, hints = '{}' + v, [scope.file.span(operands[0], operands[i - 1])] + more
                else:
                    value, hints = v, more
            elif value is not None:
                value += '{' + UrlPiece.param(RustSyntax.text(part)) + '}'
        return [] if value is None else [Value(value, node, hints)]
