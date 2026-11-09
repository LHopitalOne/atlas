"""What resolving an expression yields, and where it is resolved."""

from typing import NamedTuple


class Value(NamedTuple):
    """One string an expression can hold: the template, the node it came from, and the words that name its base
    (the expressions a leading `{}` stands for)."""

    text: str
    node: object
    hints: list


class ValueScope(NamedTuple):
    """Where an expression is resolved: its file, and whether it is joined onto a base (so a leading placeholder
    is a path parameter, not the base URL)."""

    file: object
    join: bool = False

    def joined(self, join=True):
        return self if join == self.join else self._replace(join=join)

    def moved(self, file):
        return self if file is self.file else self._replace(file=file)
