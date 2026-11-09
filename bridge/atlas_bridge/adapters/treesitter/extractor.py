"""TreeSitterExtractor: the Extractor port, implemented by handing each file to the language that reads it, plus the
service URLs in configuration files."""

from ...core.http import Extraction
from ...usecases.ports import Extractor
from .javascript import JavaScriptExtractor
from .kit import ConfigFiles, RepositoryFiles
from .python import PythonExtractor
from .rust import RustExtractor


class TreeSitterExtractor(Extractor):
    LANGUAGES = (PythonExtractor, RustExtractor, JavaScriptExtractor)

    def extract(self, repo: str, root: str) -> Extraction:
        files = RepositoryFiles(root)
        paths = files.paths()
        out = Extraction(urls=ConfigFiles(files).urls(repo))
        for language in (cls() for cls in self.LANGUAGES):
            mine = [p for p in paths if language.handles(p)]
            if mine:
                out.extend(language.extract(repo, files, mine))
        return out
