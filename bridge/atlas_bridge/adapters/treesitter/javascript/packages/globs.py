"""FolderGlobs: the folders a workspace's package globs ('packages/*', 'apps/**', '!**/test') name."""

import fnmatch
import os

from ...kit import RepositoryFiles


class FolderGlobs:
    """Expands folder globs under a root: '*' is one folder, '**' any number of them, '!glob' leaves folders out.
    Dependency and build folders are never entered, nor hidden ones unless a glob names them."""

    ANY_DEPTH = '**'
    NOT = '!'
    MAX_DEPTH = 6  # folders gone down for one glob
    MAX_FOLDERS = 5000  # folders looked at in all

    def __init__(self, root):
        self._root = root
        self._seen = 0

    def expand(self, patterns) -> list[str]:
        """The folders the globs name, sorted (a folder once)."""
        excluded = {f for p in patterns if p.startswith(self.NOT) for f in self._matches(p[1:])}
        found = {f for p in patterns if not p.startswith(self.NOT) for f in self._matches(p)}
        return sorted(found - excluded)

    def _matches(self, pattern):
        parts = [p for p in pattern.strip().strip('/').split('/') if p and p != '.']
        if any(p == '..' for p in parts):
            return set()  # only inside the workspace
        return set(self._walk(self._root, parts, 0))

    def _walk(self, folder, parts, depth):
        if not parts:
            yield folder
            return
        head, rest = parts[0], parts[1:]
        if head == self.ANY_DEPTH:
            yield from self._walk(folder, rest, depth)  # no folder at all
        for child in self._children(folder, head, depth):
            if head == self.ANY_DEPTH:
                yield from self._walk(child, parts, depth + 1)
            else:
                yield from self._walk(child, rest, depth + 1)

    def _children(self, folder, head, depth):
        if depth >= self.MAX_DEPTH or self._seen >= self.MAX_FOLDERS:
            return []
        try:
            names = sorted(os.listdir(folder))
        except OSError:
            return []
        out = []
        for name in names:
            path = os.path.join(folder, name)
            if not os.path.isdir(path) or name in RepositoryFiles.SKIP_DIRS:
                continue
            if name.startswith('.') and name != head:
                continue
            if head == self.ANY_DEPTH or fnmatch.fnmatchcase(name, head):
                self._seen += 1
                out.append(path)
        return out
