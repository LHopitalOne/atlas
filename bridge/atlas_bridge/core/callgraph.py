"""Functions and the lines that call them, across repositories: what a precise index knows that syntax alone does
not (which definition a call really reaches, even one in another repository or library)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Function:
    """A function or method definition: `key` names it the same in every repository that refers to it."""

    key: str
    name: str
    repo: str
    file: str
    start: int  # first and last line of its body, 1-based
    end: int


@dataclass(frozen=True)
class Site:
    """A line in a repository that calls a function."""

    repo: str
    file: str
    line: int
