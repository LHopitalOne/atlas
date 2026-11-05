"""Turning an expression into the values it can hold: URL templates, method names, base-URL hints."""

from abc import ABC, abstractmethod


class ValueResolver(ABC):
    """Base of the per-language expression resolvers. Dispatches on node type to a method named in HANDLERS and
    stops at MAX_DEPTH, so cyclic or very deep definitions end with no value instead of a recursion error."""

    HANDLERS: dict[str, str] = {}  # node type -> name of the method that resolves it
    MAX_DEPTH = 5

    def resolve(self, node, scope, depth=0):
        """The values `node` may hold in `scope` (whatever context the language needs), as a list."""
        if node is None or depth > self.MAX_DEPTH:
            return self.unknown(node, scope)
        handler = self.HANDLERS.get(node.type)
        if handler is None:
            return self.unknown(node, scope)
        return getattr(self, handler)(node, scope, depth)

    @abstractmethod
    def unknown(self, node, scope):
        """What an expression nobody can resolve becomes: usually a placeholder that keeps its text as a hint."""
