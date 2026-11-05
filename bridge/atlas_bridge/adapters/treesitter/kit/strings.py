"""String literals as path templates, and URL templates split into a path and the words that name its host."""

import re
from dataclasses import dataclass, field

from .syntax import Syntax


class StringTemplate:
    """The value of a string literal with every interpolation written as {name}."""

    IDENTIFIER = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')  # the last one names an interpolated expression
    STRINGS = frozenset({'string', 'template_string', 'string_literal', 'raw_string_literal'})
    CONTENT = frozenset({'string_content', 'string_fragment', 'escape_sequence'})
    INTERPOLATIONS = frozenset({'interpolation', 'template_substitution'})
    NOT_EXPRESSIONS = frozenset({'format_specifier', 'type_conversion'})

    @classmethod
    def placeholder(cls, expr: str):
        """A readable parameter name for an interpolated expression: 'request.dataset' -> 'dataset'."""
        words = cls.IDENTIFIER.findall(expr)
        return words[-1] if words else 'param'

    @classmethod
    def of(cls, node):
        """The template, or None if the node is not a string literal."""
        if node.type == 'concatenated_string':  # python "a" "b"
            parts = [cls.of(c) for c in node.named_children]
            return None if None in parts else ''.join(parts)
        if node.type not in cls.STRINGS:
            return None
        out = [cls._piece(c) for c in node.children]
        out = [p for p in out if p is not None]
        if node.type == 'raw_string_literal' and not out:
            raw = Syntax.text(node)
            return raw[raw.find('"') + 1 : raw.rfind('"')]
        return ''.join(out)

    @classmethod
    def _piece(cls, child):
        if child.type in cls.CONTENT:
            return Syntax.text(child)
        if child.type in cls.INTERPOLATIONS:
            inner = [x for x in child.named_children if x.type not in cls.NOT_EXPRESSIONS]
            return '{' + cls.placeholder(Syntax.text(inner[0]) if inner else '') + '}'
        return None


@dataclass(frozen=True)
class UrlTemplate:
    """A URL template split into its path and the words that name its host.

    'http://api:8000/orders' -> path '/orders', hints ['api']; '{BASE}/orders/{id}' -> '/orders/{id}', ['BASE'];
    '{}/x' (a positional format base) -> '/x', []; 'symbolicate' -> '/symbolicate', [].
    path is None for values that are clearly not request paths (blank, whitespace, plain words with spaces).
    """

    SCHEME = re.compile(r'^[a-z][a-z0-9+.-]*://([^/]*)', re.I)  # 'https://host:port'
    LEADING_PLACEHOLDER = re.compile(r'^\{([^{}]*)\}(?=/|$)')  # '{base}' before the first slash
    BASE_NAME = re.compile(r'url|uri|base|host|server|endpoint|addr|prefix|upstream|origin|root', re.I)

    path: str | None
    hints: list[str] = field(default_factory=list)

    @classmethod
    def split(cls, value: str) -> 'UrlTemplate':
        v = value.strip()
        if not v or ' ' in v or '\n' in v:
            return cls(None, [])
        hints = []
        m = cls.SCHEME.match(v)
        if m:
            hints.append(m.group(1).split(':')[0])
            v = v[m.end() :] or '/'
        else:
            m = cls.LEADING_PLACEHOLDER.match(v)
            if m and cls._is_base(m.group(1)):
                if m.group(1):
                    hints.append(m.group(1))
                v = v[m.end() :] or '/'
        if not v.startswith('/'):
            v = '/' + v
        return cls(v.split('?')[0].split('#')[0], hints)

    @classmethod
    def _is_base(cls, name):
        return not name or bool(cls.BASE_NAME.search(name)) or name.isupper()
