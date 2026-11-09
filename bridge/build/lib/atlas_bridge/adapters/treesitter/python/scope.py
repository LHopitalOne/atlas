"""Where an expression is read: its file, and the function and class around it."""

from dataclasses import dataclass

from .syntax import PythonSyntax


@dataclass(frozen=True, slots=True, eq=False)
class Scope:
    """A file plus the enclosing function and class (either may be None, at module level)."""

    source: object
    func: object = None
    cls: object = None

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

    @property
    def qualified(self):
        """'Class.method', 'function', or '' at module level."""
        if self.func is None:
            return ''
        name = PythonSyntax.name(self.func)
        return f'{PythonSyntax.name(self.cls)}.{name}' if self.cls is not None else name
