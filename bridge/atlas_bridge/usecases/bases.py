"""What a request's hints say about the base URL it is sent to: whether it names an API, and which path prefix."""

import re

from ..core.http import PathTemplate
from ..core.words import Words


class BaseHints:
    """Reads only the hints that are code expressions ('self.catalog_api_url', 'getConfig().LMS_BASE_URL'), not file
    paths or docstrings, which name things by accident."""

    API = 'api'
    EXPRESSION = re.compile(r'^[\w.()\[\]\'"]+$')  # a name, attribute chain, call or subscript: no '/' or spaces
    SEPARATORS = re.compile(r'[\W_]+')  # dropped when comparing a prefix with a name: 'course_modes' ~ 'coursemode'

    def __init__(self, hints):
        self._names = [h for h in hints if self.EXPRESSION.match(h)]
        self._squashed = [self._squash(h) for h in self._names]

    def names_an_api(self) -> bool:
        """A hint has the word 'api' ('catalog_api_url', 'get_api_data')."""
        return any(self.API in Words.of(h) for h in self._names)

    def mentions(self, prefix: PathTemplate) -> int:
        """How many of a prefix's own words ('course_modes' in '/api/course_modes/v1') a hint contains."""
        words = [self._squash(s.text) for s in prefix.segments if s.is_literal and not self._generic(s.text)]
        return sum(1 for w in words if w and any(w in h for h in self._squashed))

    @classmethod
    def _generic(cls, text):
        return text == cls.API or bool(PathTemplate.VERSION.match(text))

    @classmethod
    def _squash(cls, text):
        """Lower case, no separators, no plural 's': 'course_modes' -> 'coursemode'."""
        return cls.SEPARATORS.sub('', text.lower()).rstrip('s')


class PrefixOrder:
    """The order in which prefixes that fit a request equally are taken: the same base in several API versions
    ('/api/v3', '/api/v4', '/api/v5') gives the newest first, since a server keeps old versions for old clients and
    current code calls the newest; anything else by its text."""

    NUMBER = re.compile(r'\d+')

    @classmethod
    def key(cls, prefix: str) -> tuple:
        segments = prefix.split('/')
        versions = [bool(PathTemplate.VERSION.match(s)) for s in segments]
        base = '/'.join('{version}' if v else s for s, v in zip(segments, versions, strict=True))
        newest = tuple(-int(cls.NUMBER.search(s).group()) for s, v in zip(segments, versions, strict=True) if v)
        return base, newest, prefix
