"""Handlers for string literals: escapes, raw strings, implicit concatenation and f-string interpolations."""

import re

from ...kit import StringTemplate
from ..syntax import PythonSyntax
from .value import Value


class StringHandlers:
    """Mixed into a ScopeResolver: string literals as values. An f-string interpolation takes the value of its
    expression when that is a single known value, and is otherwise written as a placeholder named after it."""

    HANDLERS = {'string': 'string_values', 'concatenated_string': 'string_values'}
    ESCAPE = re.compile(r'\\(.)', re.S)  # a backslash escape; group 1 is the escaped character
    ESCAPES = {'\\': '\\', "'": "'", '"': '"', 'n': '\n', 't': '\t', 'r': '\r', '\n': ''}

    def string_values(self, node, scope, depth):
        return [self.string(node, scope, depth)]

    def string(self, node, scope, depth=0):
        """The one Value of a string literal (or of implicitly concatenated literals)."""
        if node.type == 'concatenated_string':
            parts = [self.string(c, scope, depth) for c in node.named_children if c.type == 'string']
            return Value(''.join(p.text for p in parts), frozenset().union(*(p.hints for p in parts)), Value.LITERAL)
        start = node.children[0] if node.children else None
        prefix = PythonSyntax.text(start).lower() if start is not None and start.type == 'string_start' else ''
        raw, fstr = 'r' in prefix, 'f' in prefix
        out, hints = [], set()
        for c in node.children:
            if c.type == 'string_content':
                out.append(self._content(PythonSyntax.text(c), raw, fstr))
            elif c.type == 'escape_interpolation':
                out.append(PythonSyntax.text(c)[:1])
            elif c.type == 'interpolation':
                expr = c.named_children[0] if c.named_children else None
                out.append(self._interpolation(expr, scope, depth, hints))
        return Value(''.join(out), frozenset(hints), Value.LITERAL)

    @classmethod
    def _content(cls, text, raw, fstr):
        content = text if raw else cls.unescape(text)
        return content.replace('{{', '{').replace('}}', '}') if fstr else content

    @classmethod
    def unescape(cls, text):
        return cls.ESCAPE.sub(lambda m: cls.ESCAPES.get(m.group(1), m.group(0)), text)

    def _interpolation(self, expr, scope, depth, hints):
        if expr is None:
            return '{param}'
        hints.add(Value.hint(PythonSyntax.text(expr)))
        if expr.type == 'identifier':
            vs = self.interpolated_identifier(expr, scope, depth + 1)
        else:
            vs = self.resolve(expr, scope, depth + 1)
        if len(vs) == 1 and vs[0].is_known:
            hints.update(vs[0].hints)
            return vs[0].text
        for v in vs:
            hints.update(v.hints)
        return '{' + StringTemplate.placeholder(PythonSyntax.text(expr)) + '}'
