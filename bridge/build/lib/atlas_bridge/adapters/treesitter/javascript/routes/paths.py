"""Express / Koa / Fastify / Hono path syntax."""

import re


class ExpressPath:
    """':id' -> {id}, '*' -> {*rest}: the route path syntax of Express and the frameworks that copied it."""

    WILDCARDS = frozenset({'*', '(.*)', '(.*)?'})  # segments that match the rest of the path
    # ':id', ':id?', ':id(\\d+)', Hono's ':id{[0-9]{1,3}}' (one level of nested braces)
    PARAM = re.compile(r':(\w+)(\{(?:[^{}]|\{[^{}]*\})*\}|\([^)]*\))?\??')

    @classmethod
    def canonical(cls, path):
        """The path in the canonical template syntax, with a leading slash."""
        joined = '/'.join(cls._segment(seg) for seg in path.split('/'))
        return joined if joined.startswith('/') else '/' + joined

    @classmethod
    def _segment(cls, seg):
        if seg in cls.WILDCARDS:
            return '{*rest}'
        if seg.startswith('*'):
            return '{*' + (cls._word_chars(seg) or 'rest') + '}'
        seg = cls.PARAM.sub(r'{\1}', seg)
        return '{*rest}' if '*' in seg else seg

    @staticmethod
    def _word_chars(seg):
        """The letters, digits and underscores of a segment (what \\w matches): '*rest' -> 'rest'."""
        return ''.join(c for c in seg if c.isalnum() or c == '_')

    @staticmethod
    def join(prefix, path):
        """A route path under the prefix of the router it is mounted on."""
        return (prefix.rstrip('/') + '/' + path.lstrip('/')) if prefix else path
