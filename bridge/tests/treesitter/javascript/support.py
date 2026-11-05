"""A temporary repository of javascript / typescript files, and what JavaScriptExtractor finds in it."""

import os
import tempfile

from atlas_bridge.adapters.treesitter.javascript import JavaScriptExtractor
from atlas_bridge.adapters.treesitter.javascript.policy import JavaScriptTestPolicy
from atlas_bridge.adapters.treesitter.javascript.workspace import JavaScriptWorkspace
from atlas_bridge.adapters.treesitter.kit import Grammar, RepositoryFiles, SourceFile


class Repository:
    """{path: source} written to a folder, extracted with every file handed to the extractor."""

    def __init__(self, files, repo='web'):
        self._files = files
        self._repo = repo

    def extract(self):
        with tempfile.TemporaryDirectory() as root:
            for path, source in self._files.items():
                full = os.path.join(root, path)
                os.makedirs(os.path.dirname(full), exist_ok=True)
                with open(full, 'w') as f:
                    f.write(source)
            return JavaScriptExtractor().extract(self._repo, RepositoryFiles(root), sorted(self._files))

    @classmethod
    def calls(cls, source, path='src/a.js'):
        """{(method, path): call} of one file."""
        return {(c.method, str(c.path)): c for c in cls({path: source}).extract().calls}

    @classmethod
    def routes(cls, files):
        """{(method, path): route} of the files."""
        return {(m, str(r.path)): r for r in cls(files).extract().routes for m in r.methods}

    @staticmethod
    def workspace(files, policy=None):
        """A JavaScriptWorkspace of [(path, source)], built in memory."""
        paths = JavaScriptTestPolicy()
        sources = [SourceFile(p, s.encode(), Grammar.for_path(p), paths.is_test(p)) for p, s in files]
        return JavaScriptWorkspace('web', sources, policy)
