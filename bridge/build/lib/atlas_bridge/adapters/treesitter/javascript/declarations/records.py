"""What a call declares about routes: a route of a router, or a router mounted under a prefix."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class Declaration(ABC):
    """Something one call of a file declares about its routes."""

    @abstractmethod
    def add_to(self, found):
        """Record the declaration in the FileRoutes of its file."""


@dataclass(frozen=True)
class RouteDeclaration(Declaration):
    """`app.get('/orders/:id', h)`: the route of one receiver, before the prefixes it is mounted under."""

    receiver: str
    path: str
    methods: frozenset
    handler: str
    line: int

    def add_to(self, found):
        found.add_route(self)


@dataclass(frozen=True)
class Mount(Declaration):
    """`parent.use('/prefix', child)`: child is the expression that names the mounted router."""

    parent: str
    prefix: str
    child: object = field(compare=False)

    def add_to(self, found):
        found.add_mount(self)
