"""`format!` macros as URL templates: '{}' and '{name}' become path parameters, a leading one the base."""

import re

from ...kit import StringTemplate
from ..syntax import RustSyntax
from .pieces import UrlPiece
from .value import Value


class FormatMacro:
    # '{{' and '}}' are literal braces; '{x}', '{0}', '{:?}' and '{name:>5}' are placeholders (group 1 inside).
    PLACEHOLDER = re.compile(r'\{\{|\}\}|\{([^{}]*)\}')

    @classmethod
    def read(cls, file, macro, join=False):
        """The macro's value with its arguments as {params}, or None when its format is not a literal."""
        split = cls.split(macro)
        if split is None:
            return None
        fmt, positional, named = split
        positional = [file.span(g[0], g[-1]) for g in positional]
        named = {k: file.span(g[0], g[-1]) for k, g in named.items()}
        text, hints = cls._render(fmt, positional, named, join)
        return Value(text, macro, hints)

    @classmethod
    def split(cls, macro):
        """(format string, [positional argument tokens], {name: argument tokens}) of a formatting macro, or None
        when its format is not a string literal."""
        tt = next((c for c in macro.children if c.type == 'token_tree'), None)
        if tt is None:
            return None
        groups = cls._groups(tt)
        if not groups or len(groups[0]) != 1 or groups[0][0].type not in RustSyntax.STRINGS:
            return None
        positional, named = [], {}
        for g in groups[1:]:
            if len(g) >= 3 and g[1].type == '=' and g[0].type == 'identifier':
                named[RustSyntax.text(g[0])] = g[2:]
            elif g:
                positional.append(g)
        return StringTemplate.of(groups[0][0]), positional, named

    @staticmethod
    def _groups(tt):
        """The macro's tokens split at top-level commas."""
        groups, cur = [], []
        for c in tt.children[1:-1]:
            if c.type == ',':
                groups.append(cur)
                cur = []
            else:
                cur.append(c)
        if cur:
            groups.append(cur)
        return groups

    @classmethod
    def _render(cls, fmt, positional, named, join):
        out, pos, hints, index = '', 0, [], 0
        for m in cls.PLACEHOLDER.finditer(fmt):
            out += fmt[pos : m.start()]
            pos = m.end()
            if m.group(1) is None:
                continue  # '{{' or '}}': a literal brace, never part of a path
            name = m.group(1).split(':')[0].strip()
            if not name or (name.isascii() and name.isdigit()):
                i = int(name) if name else index
                index += 0 if name else 1
                expr = positional[i] if i < len(positional) else ''
            else:
                expr = named.get(name, name)
            if not out and not join:  # a leading placeholder holds the scheme and host: the base
                hints.append(expr)
                out += '{}'
            else:
                out += '{' + UrlPiece.param(expr) + '}'
        return out + fmt[pos:], hints
