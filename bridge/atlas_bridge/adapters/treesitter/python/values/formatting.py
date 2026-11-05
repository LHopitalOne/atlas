"""`'...'.format(...)`: one format template filled with the values of its arguments."""

import itertools
import re

from ...kit import StringTemplate
from ..syntax import PythonSyntax
from .url import UrlShape
from .value import Value


class FormatCall:
    """Fills the fields of literal templates from one call's arguments.

    A field whose argument is a known value takes its text; an unknown argument in the first field is the base URL
    ('{}'), elsewhere a placeholder named after the field or the argument.
    """

    FIELD = re.compile(r'\{([^{}]*)\}')  # a replacement field; group 1 is its name, conversion and format spec

    def __init__(self, resolver, scope, pos, kw, depth):
        self._resolver = resolver
        self._scope = scope
        self._pos = pos
        self._kw = kw
        self._depth = depth

    def apply(self, template: Value):
        """The formatted value, or None when it does not read as a URL."""
        hints, base, numbering = set(template.hints), [], itertools.count()
        text = self.FIELD.sub(lambda m: self._fill(m, hints, base, numbering), template.text)
        formatted = Value(text, frozenset(hints), Value.LITERAL)
        return formatted if UrlShape.base_ok(formatted, ''.join(base)) else None

    def _fill(self, m, hints, base, numbering):
        """One field's text; adds the argument's hints, and its expression to `base` when it is an unknown base."""
        field = m.group(1).partition('!')[0].partition(':')[0]
        key, arg = self._argument(field, numbering)
        if arg is None:
            return '{' + (key or 'param') + '}'
        a = self._resolver.resolve(arg, self._scope, self._depth + 1)[0]
        hints.update(a.hints)
        if a.is_known:
            return a.text
        text = PythonSyntax.text(arg)
        hints.add(Value.hint(text))
        if m.start() == 0:
            base.append(text)
            return '{}'
        return '{' + (key or StringTemplate.placeholder(text)) + '}'

    def _argument(self, field, numbering):
        """(keyword or None, argument node or None) for a field name; '' takes the next positional argument."""
        if field == '':
            idx = next(numbering)
            return None, (self._pos[idx] if idx < len(self._pos) else None)
        if field.isdigit():
            return None, (self._pos[int(field)] if int(field) < len(self._pos) else None)
        key = field.partition('.')[0].partition('[')[0]
        return key, self._kw.get(key)
