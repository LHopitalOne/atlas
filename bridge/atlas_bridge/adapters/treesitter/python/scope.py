"""Where an expression is read: its file, and the function and class around it."""

from dataclasses import dataclass
from typing import NamedTuple

from .syntax import PythonSyntax


class Binding(NamedTuple):
    """What one call passes for a parameter: the argument (or the parameter's default) and where to read it."""

    name: str
    node: object
    scope: 'Scope'


@dataclass(frozen=True, slots=True, eq=False)
class Scope:
    """A file plus the enclosing function and class (either may be None, at module level).

    A scope read for one call of its function (`called`) carries that call's arguments as `bindings`: a parameter is
    what the call passes, and a parameter it does not pass (with no default) is unknown, not a marker for callers."""

    source: object
    func: object = None
    cls: object = None
    bindings: tuple[Binding, ...] = ()
    called: bool = False

    @classmethod
    def at(cls, source, node):
        """The scope a node sits in: its innermost function, and the class around that function (or the node)."""
        func = PythonSyntax.ancestor(node, PythonSyntax.FUNCTION)
        klass = PythonSyntax.ancestor(func if func is not None else node, PythonSyntax.CLASS)
        return cls(source, func, klass)

    @classmethod
    def module(cls, source):
        return cls(source)

    def without_function(self):
        """The same file and class, read outside any function (class attributes, parameter defaults)."""
        return Scope(self.source, None, self.cls)

    def bound(self, name) -> Binding | None:
        """What the call this scope is read for passes for parameter `name`, or None."""
        return next((b for b in self.bindings if b.name == name), None)

    @property
    def qualified(self):
        """'Class.method', 'function', or '' at module level."""
        if self.func is None:
            return ''
        name = PythonSyntax.name(self.func)
        return f'{PythonSyntax.name(self.cls)}.{name}' if self.cls is not None else name
