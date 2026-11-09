"""Route paths in axum and actix-web syntax, made canonical, joined to prefixes and read from expressions."""

import re

from ...kit import StringTemplate
from ..syntax import RustSyntax


class RoutePath:
    TAIL_CAPTURE = re.compile(r'\{[^{}]*\}\*')  # actix '{tail}*': a capture of the rest of the path
    PATTERN_CAPTURE = re.compile(r'\{[^{}*]*:[^{}]*\}')  # actix '{id:\d+}': a capture with a regex

    def __init__(self, workspace):
        self._workspace = workspace

    @classmethod
    def canonical(cls, path):
        """axum/actix route syntax -> canonical: ':x' and '{x:re}' -> {x}, '*x' and '{x}*' -> {*x}."""
        return '/'.join(cls._segment(s) for s in path.split('/'))

    @classmethod
    def _segment(cls, s):
        if s.startswith(':'):
            return '{' + s[1:] + '}'
        if s.startswith('*') and len(s) > 1:
            return '{*' + s[1:] + '}'
        if cls.TAIL_CAPTURE.fullmatch(s):
            return '{*' + s[1:-2].split(':')[0] + '}'
        if cls.PATTERN_CAPTURE.fullmatch(s):
            return '{' + s[1:].split(':')[0] + '}'
        return s

    @staticmethod
    def join(prefix, path):
        rest = path.strip('/')
        return prefix.rstrip('/') + ('/' + rest if rest else '') or '/'

    def value(self, file, node):
        """The canonical path a route argument holds: a string literal or a string const, else None."""
        node = RustSyntax.unwrap(node)
        if node is None:
            return None
        if node.type in RustSyntax.STRINGS:
            return self.canonical(StringTemplate.of(node))
        hit = self._workspace.const_value(file, node)
        if hit is not None and hit[1].type in RustSyntax.STRINGS:
            return self.canonical(StringTemplate.of(hit[1]))
        return None
