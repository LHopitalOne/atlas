"""How a resolved value reads as a URL: rendering markers, unknown bases, and whether it looks like a path."""

import re

from ...kit import UrlTemplate
from .value import Marker


class UrlShape:
    """Heuristics over resolved URL text, shared by request detection and the resolver."""

    URLISH = re.compile(r'url|uri|base|host|server|endpoint|addr|upstream|origin|domain', re.I)  # names of bases
    LEAD = re.compile(r'^\{(\w*)\}(?=[^/])')  # a base placeholder glued to the path: '{base_url}ip/{addr}'

    @classmethod
    def render(cls, text):
        """Markers as {name}; a base placeholder glued to the path gets its slash: '{}x' -> '{}/x'."""
        s = Marker.braces(text)
        m = cls.LEAD.match(s)
        if m and (not m.group(1) or cls.URLISH.search(m.group(1))):
            return s[: m.end()] + '/' + s[m.end() :]
        return s

    @classmethod
    def split(cls, text) -> UrlTemplate:
        """The rendered text split into its path and base hints."""
        return UrlTemplate.split(cls.render(text))

    @classmethod
    def base_ok(cls, value, base):
        """Whether a value built on an unknown base still reads as a URL: '{}/path' or a base named like a URL."""
        text = value.text
        return not text.startswith('{}') or text[2:3] in ('', '/', '?') or bool(cls.URLISH.search(base))

    @staticmethod
    def pathlike(raw, base, client, literals):
        """Whether a URL value looks like a request path; a client-like receiver needs less evidence.

        On another receiver, an unknown base followed only by parameters ('{}/{db}', a cache key) is not enough.
        """
        if raw.startswith('/') or '://' in raw or base:
            return True
        if raw.startswith('{}/'):
            return client or literals >= 1
        return client and (raw.startswith('{}') or '/' in raw)
