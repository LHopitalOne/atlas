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


class SourceFiles(ABC):
    """The code files of each repository, and their text."""

    @abstractmethod
    def paths(self, repo: str) -> list[str]:
        """Paths, inside the repository, of its code files that are not tests or tooling."""

    @abstractmethod
    def text(self, repo: str, path: str) -> str:
        """The file's text, or '' when it cannot be read."""


@dataclass(frozen=True)
class ReadHelper:
    """A function that sends a request whose URL is built from its own parameters: `function` sends `method` (or a
    parameter's value, '{method}') to `url`, a template whose `{name}` parts are those parameters or a base URL. Or
    (kind CLIENT) a client object made with a base URL (`axios.create({baseURL: config.api})`): `url` is that base."""

    FUNCTION = 'function'
    CLIENT = 'client'

    function: str
    method: str
    url: str
    kind: str = FUNCTION

    @property
    def name(self) -> str:
        """The name other files use it by: the last part of 'Client.send'."""
        return self.function.split('.')[-1]


@dataclass(frozen=True)
class ReadRequest:
    """A request a reader says a file sends: on `line`, whose code is `code`; `url` as far as the file shows it
    (`{name}` for a part it does not, a leading `{base}` for a base URL from elsewhere). `base`: the expression the
    base URL comes from; `service`: words in the code naming where it goes; `through`: the helper it is sent with."""

    line: int
    code: str
    method: str
    url: str
    protocol: str
    function: str = ''
    base: str = ''
    service: str = ''
    through: str = ''


@dataclass(frozen=True)
class ReadRoute:
    """A route or channel a reader says a file serves or consumes: an HTTP route, a task or job handler, a queue or
    topic consumer, declared on `line` (whose code is `code`) for `path` (a route path, or a channel's name as the
    code writes it), handled by `function`."""

    line: int
    code: str
    method: str
    path: str
    protocol: str
    function: str = ''


@dataclass(frozen=True)
class FileReading:
    """What a reader found in one file: the requests it sends, the helpers it defines, and what it serves."""

    requests: tuple[ReadRequest, ...] = ()
    helpers: tuple[ReadHelper, ...] = ()
    routes: tuple[ReadRoute, ...] = ()


@dataclass(frozen=True)
class ReadCase:
    """A file to read for requests, with its text (numbered by the reader) and the helpers of its repository that it
    calls, defined in other files."""

    repo: str
    path: str
    text: str
    helpers: tuple[ReadHelper, ...] = ()


class RequestReader(ABC):
    """Reads files and says which requests each sends: a language model, so every claim is checked against the code
    before it is used (usecases.reading.ReadCheck)."""

    model: str = ''

    @abstractmethod
    def read(self, cases: list[ReadCase]) -> list[FileReading | None]:
        """One FileReading per case, in order; None for a file it could not read."""
