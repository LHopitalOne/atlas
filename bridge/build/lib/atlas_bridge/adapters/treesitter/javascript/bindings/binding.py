"""What a name refers to at a point of a file: a declaration with a value, or a parameter."""

from abc import ABC, abstractmethod

from ..syntax.members import Members


class Binding(ABC):
    """The nearest binding of a name around a node. Subclasses say whether the bound value can be read."""

    def __init__(self, node):
        self._node = node

    @property
    def node(self):
        """The initializer of a declaration, or the parameter (or destructuring declarator) that binds the name."""
        return self._node

    @property
    @abstractmethod
    def initializer(self):
        """The expression the name is bound to, or None when it is bound to no value we can read."""

    @abstractmethod
    def annotated_type(self, name) -> str:
        """The type the binding is annotated with for `name` (`api: Client` -> 'Client'), or ''."""


class ValueBinding(Binding):
    """`const name = value`: a name declared with an initializer we can read."""

    @property
    def initializer(self):
        return self._node

    def annotated_type(self, name) -> str:
        return ''


class ParamBinding(Binding):
    """A parameter, a for-in/of variable, a catch parameter or a destructured declaration (`const {api} = props`):
    bound, but to no value we can read."""

    @property
    def initializer(self):
        return None

    def annotated_type(self, name) -> str:
        return Members.param_type(self._node, name)
