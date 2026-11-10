"""Repository paths as Python modules see them: always with '/' between folders."""

from ..kit import RepositoryFiles


class SlashedFiles(RepositoryFiles):
    """A repository's files listed with '/' separators (as module names and emitted files need them), read through
    the paths the repository gave, which use '\\' when they come from a directory walk on Windows."""

    def __init__(self, files: RepositoryFiles, paths: list[str]):
        super().__init__(files.root)
        self._files = files
        self._listed = [self.slashed(p) for p in paths]
        self._originals = dict(zip(self._listed, paths, strict=True))

    @staticmethod
    def slashed(path: str) -> str:
        return path.replace('\\', '/')

    def listed(self) -> list[str]:
        """The paths, with '/' separators, in the order given."""
        return list(self._listed)

    def read(self, path: str) -> bytes:
        return self._files.read(self._originals.get(path, path))
