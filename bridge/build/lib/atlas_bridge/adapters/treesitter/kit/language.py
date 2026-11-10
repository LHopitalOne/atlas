"""LanguageExtractor: the template every language follows to turn a repository's files into routes and calls."""

from abc import ABC, abstractmethod

from ....core.errors import SourceReadError
from ....core.http import Extraction
from .files import RepositoryFiles, TestPathPolicy
from .grammar import Grammar
from .source import SourceFile
from .workspace import Workspace


class LanguageExtractor(ABC):
    """Reads every file of its grammars once, builds one workspace, and runs each collector over it.

    Subclasses name their grammars and test policy, and implement workspace() and collectors().
    """

    GRAMMARS: frozenset[str] = frozenset()
    POLICY = TestPathPolicy

    def handles(self, path: str) -> bool:
        return Grammar.BY_EXTENSION.get(path[path.rfind('.') :]) in self.GRAMMARS

    def extract(self, repo: str, files: RepositoryFiles, paths: list[str]) -> Extraction:
        policy = self.POLICY()
        sources = []
        for path in paths:
            try:
                data = files.read(path)
            except SourceReadError:
                continue  # unreadable or oversized: nothing to find in it
            sources.append(SourceFile(path, data, Grammar.for_path(path), policy.is_test(path)))
        workspace = self.workspace(repo, sources)
        out = Extraction()
        for collector in self.collectors(workspace):
            out.extend(collector.collect())
        return out

    @abstractmethod
    def workspace(self, repo: str, sources: list[SourceFile]) -> Workspace: ...

    @abstractmethod
    def collectors(self, workspace: Workspace) -> list: ...
