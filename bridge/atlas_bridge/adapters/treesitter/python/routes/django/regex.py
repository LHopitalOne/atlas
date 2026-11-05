"""Django URL regexes as path templates: a small hand parser for the regex subset URLconfs use."""

import re


class DjangoRegex:
    """'^(?P<id>[^/]+)/(?:a|b)/?$' -> ['{id}/a', '{id}/b'].

    Named groups become parameters ('{*name}' when they match '.*' or '.+'), unnamed groups and classes become
    '{param}', optional parts are dropped, alternations expand (at most MAX_ALTS), anchors and lookarounds vanish.
    """

    MAX_ALTS = 8  # paths one URLconf entry may expand to

    @classmethod
    def templates(cls, rx: str) -> list[str]:
        return list(dict.fromkeys(_RegexParser(rx).sequence()))[: cls.MAX_ALTS] or ['']


class _RegexParser:
    """One pattern being read left to right: the text and the position reached."""

    DOTSTAR = re.compile(r'(?<!\\)\.[*+]')  # an unescaped '.*' or '.+': the group takes the rest of the path
    QUANTIFIER = re.compile(r'(\*|\+|\?|\{\d*,?\d*\})[?+]?')  # a quantifier, possibly lazy or possessive
    WILD_ESCAPES = 'dwsDWS'  # \d, \w, ...: a parameter
    EMPTY_ESCAPES = 'bBAZz'  # \b, \A, ...: assertions that match no text

    def __init__(self, rx: str):
        self._s = rx
        self._pos = 0

    def sequence(self):
        """The alternatives of the sequence from the current position up to an unmatched ')' or the end."""
        s = self._s
        branches, cur = [], ['']
        while self._pos < len(s) and s[self._pos] != ')':
            if s[self._pos] == '|':
                branches += cur
                cur = ['']
                self._pos += 1
                continue
            kind, opts = self.atom()
            m = self.QUANTIFIER.match(s, self._pos)
            if m:
                self._pos = m.end()
                opts = self._quantified(kind, opts, m.group(1))
            cur = [a + b for a in cur for b in opts][: DjangoRegex.MAX_ALTS]
        return branches + cur

    def atom(self):
        """(kind, alternatives) of the atom at the current position, which moves past it: 'lit', 'wild', 'group' or
        'dot'."""
        s, i = self._s, self._pos
        c = s[i]
        if c == '(':
            return self.group()
        if c == '[':
            self._pos = self._class_end(i) + 1
            return 'wild', ['{param}']
        if c == '\\':
            self._pos = i + 2
            return self._escape(s[i + 1 : i + 2])
        self._pos = i + 1
        if c in '^$':
            return 'lit', ['']
        if c == '.':
            return 'dot', ['.']
        return 'lit', [c]

    def _escape(self, n):
        if n and n in self.WILD_ESCAPES:
            return 'wild', ['{param}']
        if n and n in self.EMPTY_ESCAPES:
            return 'lit', ['']
        return 'lit', [n]

    def group(self):
        """(kind, alternatives) of the group opening at the current position, which moves past its ')'."""
        i = self._pos
        j = self._close(i)
        self._pos = j + 1
        inner = self._s[i + 1 : j]
        if inner.startswith('?P<'):
            k = inner.find('>')
            name, body = inner[3:k], inner[k + 1 :]
            return 'wild', ['{*' + name + '}' if self.DOTSTAR.search(body) else '{' + name + '}']
        if inner.startswith('?:'):
            return 'group', _RegexParser(inner[2:]).sequence()
        if inner.startswith('?P='):
            return 'wild', ['{param}']
        if inner.startswith('?'):  # lookaround, inline flags, comment
            return 'lit', ['']
        return 'wild', ['{*param}' if self.DOTSTAR.search(inner) else '{param}']

    @staticmethod
    def _quantified(kind, opts, q):
        optional = q in ('?', '*') or q.startswith(('{0', '{,'))
        if kind == 'dot':
            return ['{*path}']
        if kind == 'wild':
            return [''] if q == '?' else opts
        return [''] if optional else opts

    def _close(self, i):
        """The index of the ')' that closes the group opening at i (len when unclosed)."""
        s, depth, j = self._s, 0, i
        while j < len(s):
            c = s[j]
            if c == '\\':
                j += 2
                continue
            if c == '[':
                j = self._class_end(j)
            elif c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
                if depth == 0:
                    return j
            j += 1
        return len(s)

    def _class_end(self, i):
        """The index of the ']' that closes the character class opening at i (len when unclosed)."""
        s, j = self._s, i + 1
        if s[j : j + 1] == '^':
            j += 1
        if s[j : j + 1] == ']':
            j += 1
        while j < len(s):
            if s[j] == '\\':
                j += 2
                continue
            if s[j] == ']':
                return j
            j += 1
        return len(s)
