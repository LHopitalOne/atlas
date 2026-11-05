"""Routes as router evaluation finds them, before they become Route entities."""

from typing import NamedTuple

from .paths import RoutePath


class FoundRoute(NamedTuple):
    """A route relative to where its router is mounted, and the file and line that declare it."""

    path: str
    methods: set
    handler: str
    file: object
    line: int

    def under(self, prefix: str) -> 'FoundRoute':
        """The same route mounted under a prefix."""
        return self._replace(path=RoutePath.join(prefix, self.path))


class AttributeRoute(NamedTuple):
    """An actix-web attribute route, `#[get("/p")] fn handler`: its path, methods, line, file and fn node."""

    path: str
    methods: set
    line: int
    file: object
    fn: object
