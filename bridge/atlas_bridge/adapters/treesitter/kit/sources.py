"""The code files of the repositories and their text, for a reader that looks at whole files (usecases.read)."""

import os

from ....core.errors import SourceReadError
from ....usecases.ports import SourceFiles
from .files import RepositoryFiles, TestPathPolicy


class RepositorySources(SourceFiles):
    """Code files in the languages Atlas reads and a few it does not parse but a reader can (Go, Java, Ruby...),
    leaving out tests, tooling, minified bundles and files too large to be hand-written. Texts are read on demand and
    the last ones kept, since a reading pass asks for the same files twice."""

    EXTENSIONS = frozenset(
        {'.py', '.rs', '.js', '.mjs', '.cjs', '.jsx', '.ts', '.tsx', '.vue', '.svelte'}
        | {'.go', '.java', '.kt', '.rb', '.php', '.cs', '.swift', '.scala', '.ex', '.exs'}
    )
    MINIFIED = ('.min.js', '.bundle.js', '.d.ts')
    MAX_BYTES = 200_000  # larger files are generated or bundled
    KEPT = 4000  # texts kept in memory

    def __init__(self, roots: dict[str, str], is_test=None):
        self._files = {repo: RepositoryFiles(root) for repo, root in roots.items()}
        self._is_test = is_test or TestPathPolicy().is_test
        self._texts = {}

    def paths(self, repo: str) -> list[str]:
        files = self._files.get(repo)
        if files is None:
            return []
        return [p for p in files.all_paths() if self._wanted(p)]

    def text(self, repo: str, path: str) -> str:
        key = (repo, path)
        if key not in self._texts:
            if len(self._texts) >= self.KEPT:
                self._texts.pop(next(iter(self._texts)))
            self._texts[key] = self._read(repo, path)
        return self._texts[key]

    def _wanted(self, path):
        return (
            os.path.splitext(path)[1] in self.EXTENSIONS
            and not path.endswith(self.MINIFIED)
            and not self._is_test(path)
        )

    def _read(self, repo, path):
        files = self._files[repo]
        try:
            if os.path.getsize(os.path.join(files.root, path)) > self.MAX_BYTES:
                return ''
            return files.read(path).decode('utf-8', 'replace')
        except (OSError, SourceReadError):
            return ''
