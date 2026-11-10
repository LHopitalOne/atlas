"""Ports: what the use cases need from the outside world, as abstract classes adapters implement."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..core.callgraph import Function, Site, Target
from ..core.descriptions import Description
from ..core.evidence import Assumption, Verdict
from ..core.http import Call, Extraction, Route


class Extractor(ABC):
    """Finds the HTTP routes a repository serves and the requests it sends."""

    @abstractmethod
    def extract(self, repo: str, root: str) -> Extraction:
        """repo: the repository's name in the results; root: its folder."""

    def is_test(self, path: str) -> bool:
        """Whether a file (a path inside a repository) is test or tooling code; by default none is."""
        return False


class DefinitionOracle(ABC):
    """Knows, from a precise index (a compiler's view of the code), where each name in a repository is defined."""

    @abstractmethod
    def covers(self, repo: str) -> bool:
        """Whether there is an index for this repository at all."""

    @abstractmethod
    def check(self, repo: str, assumption: Assumption) -> Verdict:
        """What the index says of one assumption made while reading `repo`."""


class CallGraph(ABC):
    """Knows, from precise indexes of several repositories, which function a line is in and every line that calls a
    function, including calls from one repository into another (a service calling a client library)."""

    @abstractmethod
    def enclosing(self, repo: str, file: str, line: int) -> Function | None:
        """The innermost function whose body holds that line, or None (module level, or no index)."""

    @abstractmethod
    def callers(self, function: Function) -> list[Site]:
        """Every line, in any indexed repository, that calls the function (a function of a library read alongside)."""

    @abstractmethod
    def resolves(self, repo: str, file: str, line: int, name: str) -> frozenset[Target]:
        """What `name`, used on that line, refers to; empty when the index does not know."""


class ChannelMentions(ABC):
    """Finds where a repository names a channel (a topic, queue or pub/sub channel) as a whole string or config
    value, outside tests."""

    @abstractmethod
    def mentions(self, repo: str, name: str) -> list[tuple[str, int, str]]:
        """[(file, line, the text around it)] of each place `repo` names `name`."""


@dataclass(frozen=True)
class JudgeCase:
    """A request the rules could not settle, and the routes the code leaves possible for it."""

    call: Call
    candidates: tuple[Route, ...]


@dataclass(frozen=True)
class Choice:
    """Which candidate a judge picked (an index into the case's candidates), or None for none of them, and how sure."""

    index: int | None
    probability: float


class RouteJudge(ABC):
    """Picks, for a request, the route that receives it among a few candidates, reading the code around the call.
    Selects, never invents: it can only answer with a candidate or none."""

    @abstractmethod
    def choose(self, cases: list[JudgeCase]) -> list[Choice]:
        """One Choice per case, in order."""


@dataclass(frozen=True)
class FileCase:
    """A file of a repository to describe."""

    repo: str
    path: str


class FileDescriber(ABC):
    """Says what files do: a one-sentence summary, a role and a few tags, read from each file's code."""

    @abstractmethod
    def describe(self, cases: list[FileCase]) -> list[Description | None]:
        """One Description per case, in order; None for a file it could not describe."""
