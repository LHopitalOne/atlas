"""DeclarationSyntax: the base of every way a call declares something about routes."""

from abc import ABC, abstractmethod

from ..syntax.nodes import JsSyntax
from ..syntax.site import CallSite
from .records import Declaration


class DeclarationSyntax(ABC):
    """One way of declaring a route or a mount, read from a call site of a file."""

    @abstractmethod
    def declaration(self, site: CallSite) -> Declaration | None:
        """What the call declares, or None."""

    @staticmethod
    def is_string(node):
        return JsSyntax.unwrap(node).type == 'string'
