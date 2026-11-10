"""URL templates as text: which parts are known, which look like a path, and how pieces are glued together."""

import re

from ...kit import Syntax, UrlTemplate


class UrlText:
    PLACEHOLDER = re.compile(r'\{[^{}]*\}')  # an unknown part of a template: '{id}', '{*rest}', '{}'
    WORD_OR_SLASH = re.compile(r'[\w/]')  # something to match a route with, once the placeholders are gone
    TAIL = re.compile(r'\{[^{}*]+\}')  # a whole value that is one unknown (not already a rest) part
    LEADING_BASE = re.compile(r'^\{([^{}]*)\}/')  # '{BASE}/...': a variable in front of the first slash
    ROUTE_PARAM = re.compile(r'(?<=/)[:$]([A-Za-z_]\w*)')  # '/:id' or '/$org' written into a request path
    PATH_NAME = re.compile(r'url|uri|path|endpoint|route|href', re.I)  # an expression that holds a path or URL
    SCHEME = re.compile(r'^(?:[a-z][a-z0-9+.-]*|\{[^{}]*\})://', re.I)  # 'https://', '{protocol}://' at the start
    AUTHORITY = re.compile(r'^[a-z][a-z0-9+.-]*://[^/]*', re.I)  # 'https://host:port' up to the path
    WORD = re.compile(r'\w')
    REST = re.compile(r'\{\*([^{}]*)\}')  # '{*path}': a tail made of a path variable
    PUBLIC_HOST = re.compile(r'^[a-z][a-z0-9+.-]*://[a-z0-9-]+(?:\.[a-z0-9-]+)+(?::\d+)?$', re.I)  # a dotted name

    @classmethod
    def literal(cls, value):
        """The template has a known part (it is not made of placeholders only)."""
        return bool(cls.PLACEHOLDER.sub('', value or ''))

    @classmethod
    def matchable(cls, value):
        """Something other than placeholders and punctuation is known: a word or a slash."""
        return bool(cls.WORD_OR_SLASH.search(cls.PLACEHOLDER.sub('', value)))

    @classmethod
    def untailed(cls, value):
        """Tails as plain placeholders, '/{*path}' -> '/{path}': the name a caller's argument fills in."""
        return cls.REST.sub(r'{\1}', value)

    @classmethod
    def unknown_path(cls, value):
        """A URL whose host is known but whose path is all unknown: 'https://api.example.com/{*path}'. Nothing in it
        says which route it asks for (the path is filled in elsewhere)."""
        m = cls.AUTHORITY.match(value)
        rest = value[m.end() :] if m else ''
        return bool(cls.PLACEHOLDER.search(rest)) and not cls.WORD.search(cls.PLACEHOLDER.sub('', rest))

    @classmethod
    def value_segments(cls, value):
        """The names of the placeholders that make up the path of a URL with a public host when each stands for one
        value, not a path: 'https://lookup.binlist.net/{bin}' -> ['bin']. None for any other URL: a tail
        ('{*path}'), a name that holds a path ('{endpoint}'), a host of no public name ('http://{host}/{id}')."""
        m = cls.AUTHORITY.match(value)
        if m is None or not cls.PUBLIC_HOST.match(m.group(0)):
            return None
        names = cls.PLACEHOLDER.findall(value[m.end() :])
        if not names or any('*' in n or cls.PATH_NAME.search(n) for n in names):
            return None
        return [n[1:-1] for n in names]

    @classmethod
    def path_like(cls, value):
        """'/x', 'http://h/x', or '{BASE}/x' where the leading variable is a base URL."""
        if value.startswith('/') or cls.SCHEME.match(value):
            return True
        m = cls.LEADING_BASE.match(value)
        return bool(m) and cls.is_base_name(m.group(1))

    @staticmethod
    def is_base_name(name):
        """A variable named like a base URL ('API_URL', 'baseUrl', 'HOST'). The rule of UrlTemplate (the kit keeps it
        private), except that an empty name ('{}/x') is not a base name here."""
        return bool(name) and (bool(UrlTemplate.BASE_NAME.search(name)) or name.isupper())

    @classmethod
    def with_params(cls, value):
        """Route-style parameters in a request path as placeholders: '/projects/$org/:id' -> '/projects/{org}/{id}'."""
        return cls.ROUTE_PARAM.sub(r'{\1}', value)

    @classmethod
    def join(cls, left, right, right_node):
        """left + right. A path held in a variable glued to a literal ('/api/0' + apiUrl) is a tail: {*apiUrl}."""
        if (
            left
            and left[-1] not in '/}'
            and cls.TAIL.fullmatch(right or '')
            and cls.PATH_NAME.search(Syntax.text(right_node))
        ):
            return left + '/{*' + right[1:]
        return left + right
