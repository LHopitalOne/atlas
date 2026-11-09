"""Small judgements on pieces of URLs: is it a path, what to call an interpolated expression."""

import re

from ...kit import StringTemplate


class UrlPiece:
    # Calls that convert a value without changing it: `id.to_string()`, `url.clone()`, `x.unwrap()`.
    CONVERSIONS = frozenset(
        {'clone', 'to_string', 'to_owned', 'into', 'as_str', 'as_ref', 'unwrap', 'expect', 'into_owned'}
    )
    LEADING_BASE = re.compile(r'^\{[^{}]*\}/')  # a placeholder base followed by a path: '{base}/x'

    @staticmethod
    def path_like(v):
        """A request path, a full URL or a placeholder base followed by a path."""
        return v.startswith('/') or '://' in v or bool(UrlPiece.LEADING_BASE.match(v))

    @classmethod
    def param(cls, expr):
        """A parameter name for an interpolated expression, skipping conversions: '&id.to_string()' -> 'id'."""
        words = [w for w in StringTemplate.IDENTIFIER.findall(expr) if w not in cls.CONVERSIONS]
        return StringTemplate.placeholder(words[-1] if words else expr)
