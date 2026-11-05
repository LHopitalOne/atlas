"""Running RustExtractor over a small repository written to a temporary folder."""

import os
import tempfile

from atlas_bridge.adapters.treesitter.kit import RepositoryFiles
from atlas_bridge.adapters.treesitter.rust import RustExtractor


class RustRepo:
    """{path: source} written to a temporary repository; extract() reads every file plus one that is missing."""

    def __init__(self, files, repo='svc'):
        self.files = {'src/client.rs': files} if isinstance(files, str) else files
        self.repo = repo

    def extract(self):
        with tempfile.TemporaryDirectory() as root:
            for path, source in self.files.items():
                full = os.path.join(root, path)
                os.makedirs(os.path.dirname(full), exist_ok=True)
                with open(full, 'wb') as f:
                    f.write(source if isinstance(source, bytes) else source.encode())
            return RustExtractor().extract(self.repo, RepositoryFiles(root), sorted(self.files) + ['missing.rs'])

    def routes(self):
        """{(method, path): route}."""
        return {(m, str(r.path)): r for r in self.extract().routes for m in r.methods}

    def calls(self):
        """{(method, path): call}."""
        return {(c.method, str(c.path)): c for c in self.extract().calls}
