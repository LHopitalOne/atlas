"""Uses of names and the definitions they reach, as a precise index (SCIP) records them: what turns a code graph's
guessed edges into ones a compiler-grade tool has seen."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Definition:
    """Where a function, class or other named thing is defined: `key` names it the same in every index."""

    key: str
    name: str
    repo: str
    file: str
    line: int  # 1-based line of its name


@dataclass(frozen=True)
class Use:
    """A line that uses a definition (a call, a reference, a type in a signature). `within` is the definition the line
    sits in (the enclosing function or class), None at module level."""

    line: int
    key: str
    within: Definition | None = None
