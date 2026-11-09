"""TreeSitterExtractor: the Extractor port, implemented by handing each file to the language that reads it, plus the
service URLs in configuration files."""

from ...core.http import Extraction
from ...usecases.ports import Extractor
from .javascript import JavaScriptExtractor
from .kit import ConfigFiles, RepositoryFiles, TestPathPolicy
from .python import PythonExtractor
from .rust import RustExtractor


class TreeSitterExtractor(Extractor):
    LANGUAGES = (PythonExtractor, RustExtractor, JavaScriptExtractor)

    def __init__(self, graph=None):
        self._graph = graph  # a CallGraph from SCIP indexes: when given, it decides what syntax alone would guess

    def extract(self, repo: str, root: str) -> Extraction:
        files = RepositoryFiles(root)
        paths = files.paths()
        out = Extraction(urls=ConfigFiles(files).urls(repo))
        for language in (cls(self._graph) for cls in self.LANGUAGES):
            mine = [p for p in paths if language.handles(p)]
            if mine:
                out.extend(language.extract(repo, files, mine))
        return out

    def is_test(self, path: str) -> bool:
        """By the conventions of the language that reads the file, else the shared ones."""
        language = next((cls() for cls in self.LANGUAGES if cls().handles(path)), None)
        policy = language.POLICY() if language is not None else TestPathPolicy()
        return policy.is_test(path)
