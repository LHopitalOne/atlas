"""The files of a repository: which to read, reading them, and which are tests or tooling."""

import os
import re
import subprocess

from ....core.errors import SourceReadError
from .grammar import Grammar


class TestPathPolicy:
    """Decides from a path alone whether a file is test or tooling code. Languages subclass it to add their own
    conventions."""

    TEST_DIRS = frozenset(
        {'tests', 'test', 'testutils', 'testing', 'fixtures', '__tests__', '__mocks__', 'e2e', 'benches', 'examples'}
    )
    TEST_FILE = re.compile(r'(^test_.*\.py$|_test\.py$|^conftest\.py$|\.(spec|test)\.[jt]sx?$|_test\.rs$)')

    def is_test(self, path: str) -> bool:
        parts = path.replace('\\', '/').split('/')
        return any(p in self.TEST_DIRS for p in parts[:-1]) or bool(self.TEST_FILE.search(parts[-1]))


class RepositoryFiles:
    """The files under a repository folder: those some grammar can read, and every file (for configuration)."""

    SKIP_DIRS = frozenset(
        {'.git', 'node_modules', '.venv', 'venv', 'target', 'dist', 'build', '__pycache__', '.tox', 'vendor'}
        | {'graphify-out', '.next', '.nuxt', 'coverage', '.mypy_cache', '.pytest_cache'}  # tools' output, not code
    )
    MAX_BYTES = 2_000_000  # generated or minified files are not worth parsing
    GIT_FILES = ['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard']

    def __init__(self, root: str):
        self.root = root
        self._all = None

    def paths(self) -> list[str]:
        """Relative paths of the files a grammar reads, sorted."""
        return [p for p in self.all_paths() if os.path.splitext(p)[1] in Grammar.BY_EXTENSION]

    def all_paths(self) -> list[str]:
        """Every relative path, sorted. Uses git when the folder is a repository: tracked files and new ones it does
        not ignore (honours .gitignore); read once."""
        if self._all is None:
            try:
                out = subprocess.run(self.GIT_FILES, cwd=self.root, capture_output=True, check=True).stdout
                paths = [p for p in out.decode('utf-8', 'replace').split('\0') if p and not self._skipped(p)]
            except (OSError, subprocess.CalledProcessError):
                paths = self._walk()
            self._all = sorted(paths)
        return self._all

    def read(self, path: str) -> bytes:
        full = os.path.join(self.root, path)
        try:
            if os.path.getsize(full) > self.MAX_BYTES:
                raise SourceReadError(path, f'larger than {self.MAX_BYTES} bytes')
            with open(full, 'rb') as f:
                return f.read()
        except OSError as e:
            raise SourceReadError(path, e.strerror or str(e)) from e

    def _skipped(self, path):
        """In a folder never read (dependencies, build and tool output), even when git lists it."""
        return any(part in self.SKIP_DIRS for part in path.split('/')[:-1])

    def _walk(self):
        paths = []
        for d, dirs, files in os.walk(self.root):
            dirs[:] = [x for x in dirs if x not in self.SKIP_DIRS]
            paths += [os.path.relpath(os.path.join(d, f), self.root) for f in files]
        return paths
