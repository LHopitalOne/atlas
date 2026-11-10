"""Entities: a code graph as files, the symbols in them, and the links between them.

Knows nothing about Graphify, Atlas, files on disk or any parser. Adapters translate to and from this.
"""

from dataclasses import dataclass, field
from enum import IntEnum


class Status(IntEnum):
    """How sure we are that a link is real. The values are Atlas's edge statuses."""

    MATCHED = 0  # read directly from the code
    AMBIGUOUS = 1  # the link exists, but its target is uncertain
    UNMATCHED = 2  # the caller expects something nothing provides
    INFERRED = 3  # derived by resolution or heuristics

    @property
    def certainty(self):
        """Lower is more certain: a matched link beats an inferred one, which beats an ambiguous guess."""
        return (0, 2, 3, 1)[self]


class Kind(IntEnum):
    FUNCTION = 1
    CLASS = 2
    OTHER = 3  # constants, variables, document sections


@dataclass(frozen=True)
class Symbol:
    id: str
    name: str
    kind: Kind
    line: int = 0


@dataclass(frozen=True)
class Community:
    id: int
    name: str


@dataclass
class SourceFile:
    repo: str
    path: str
    community: Community | None = None
    symbols: list[Symbol] = field(default_factory=list)

    @property
    def ref(self):
        return Ref(self.repo, self.path)


@dataclass(frozen=True)
class Ref:
    """Points at a file (symbol is None) or at one symbol in it."""

    repo: str
    path: str
    symbol: str | None = None


@dataclass
class CodeGraph:
    files: dict[tuple[str, str], SourceFile] = field(default_factory=dict)
    links: dict[tuple[Ref, Ref], Status] = field(default_factory=dict)
    tools: set[str] = field(default_factory=set)  # what produced it, e.g. "Graphify 0.9.101"

    def file(self, repo, path):
        key = (repo, path)
        if key not in self.files:
            self.files[key] = SourceFile(repo, path)
        return self.files[key]

    def link(self, source: Ref, target: Ref, status: Status):
        """Record that source uses target. Self-links are dropped; a repeated link keeps its most certain status."""
        if source == target:
            return
        old = self.links.get((source, target))
        if old is None or status.certainty < old.certainty:
            self.links[(source, target)] = status
