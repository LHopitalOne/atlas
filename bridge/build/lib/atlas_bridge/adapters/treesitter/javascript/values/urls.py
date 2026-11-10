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

    @classmethod
    def literal(cls, value):
        """The template has a known part (it is not made of placeholders only)."""
        return bool(cls.PLACEHOLDER.sub('', value or ''))

    @classmethod
    def matchable(cls, value):
        """Something other than placeholders and punctuation is known: a word or a slash."""
        return bool(cls.WORD_OR_SLASH.search(cls.PLACEHOLDER.sub('', value)))

    @classmethod
    def path_like(cls, value):
        """'/x', 'http://h/x', or '{BASE}/x' where the leading variable is a base URL."""
        if value.startswith('/') or '://' in value:
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
