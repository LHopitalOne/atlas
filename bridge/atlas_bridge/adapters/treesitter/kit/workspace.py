"""A repository's files of one language, with the indexes collectors share."""

from abc import ABC, abstractmethod

from .source import SourceFile


class Workspace(ABC):
    """Everything collectors may look up across a repository. Languages subclass it to add their own indexes
    (modules, functions, imports, bindings), built once and shared by every collector."""

    def __init__(self, repo: str, sources: list[SourceFile]):
        self.repo = repo
        self.sources = sources
        self._by_path = {s.path: s for s in sources}
        self.index()

    @abstractmethod
    def index(self):
        """Build the language's repo-wide indexes from self.sources. Called once, at the end of __init__."""

    def source(self, path: str) -> SourceFile | None:
        return self._by_path.get(path)

    def is_test(self, source: SourceFile, node=None) -> bool:
        """Test or tooling code: by path, or (languages override this) by the code around the node."""
        return source.test
