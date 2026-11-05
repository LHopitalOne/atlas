"""Handlers for the operators that build URLs: `base + '/path'` and `'/p/%s' % x`."""

import re

from ..syntax import PythonSyntax
from .url import UrlShape
from .value import Value


class OperatorHandlers:
    """Mixed into a ScopeResolver: `+` concatenates the values of its operands (an unknown first operand is the base
    URL, written '{}'); `%` formats a literal, turning each conversion into a placeholder."""

    HANDLERS = {'binary_operator': 'binary'}
    NAMED_CONVERSION = re.compile(r'%\((\w+)\)[sdifr]')  # '%(name)s': a named conversion
    CONVERSION = re.compile(r'%[sdifr]')  # '%s', '%d', ...: a positional conversion

    def binary(self, node, scope, depth):
        op = node.child_by_field_name('operator').type
        if op == '+':
            return self.concat(node, scope, depth)
        if op == '%':
            return self.percent(node, scope, depth)
        return self.unknown(node)

    @staticmethod
    def _operands(node):
        """The operands of a chain of `+`, left to right."""
        ops, n = [], node
        while n.type == 'binary_operator' and n.child_by_field_name('operator').type == '+':
            ops.append(n.child_by_field_name('right'))
            n = n.child_by_field_name('left')
        ops.append(n)
        ops.reverse()
        return ops

    def concat(self, node, scope, depth):
        ops = self._operands(node)
        first = PythonSyntax.text(ops[0])
        acc = self.resolve(ops[0], scope, depth + 1)
        if all(v.is_unknown for v in acc):  # an unknown first operand is the base URL
            hints = frozenset().union(*(v.hints for v in acc)) | {Value.hint(first)}
            acc = [Value('{}', hints, Value.UNKNOWN)]
        for op in ops[1:]:
            acc = self.join(acc, self.resolve(op, scope, depth + 1))
        acc = [v for v in acc if UrlShape.base_ok(v, first)]  # name + '_state' is a key, not a URL
        if all(v.is_unknown for v in acc):  # no string in sight: arithmetic, not a URL
            return self.unknown(node)
        return acc

    def percent(self, node, scope, depth):
        right = Value.hint(PythonSyntax.text(node.child_by_field_name('right')))
        out = []
        for v in self.resolve(node.child_by_field_name('left'), scope, depth + 1):
            if not v.is_literal:
                continue
            s = '{}' + v.text[2:] if v.text.startswith('%s') else v.text
            s = self.NAMED_CONVERSION.sub(r'{\1}', s)
            s = self.CONVERSION.sub('{param}', s).replace('%%', '%')
            out.append(Value(s, v.hints | {right}, Value.LITERAL))
        return out
