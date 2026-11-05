"""A request read from the code whose client's base path is not known yet."""

from dataclasses import dataclass

from ...kit import SourceFile
from ..clients.registry import ClientRegistry
from ..clients.specs import ClientSpec


@dataclass(frozen=True)
class PendingRequest:
    """Everything about a request but the base path of its client, which the repository's other files decide."""

    source: SourceFile
    line: int
    method: str
    function: str
    hints: frozenset
    test: bool
    path: str  # the path as written at the call
    client: ClientSpec | None  # the client it is sent with, when something says where that comes from

    def full_path(self, clients: ClientRegistry):
        """The path with the client's base path in front of it; the path as written when there is no client."""
        return clients.prefixed(self.path, self.client) if self.client is not None else self.path
