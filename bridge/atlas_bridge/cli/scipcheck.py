"""The optional SCIP check of the map command: index each repository it can, verify the links, and say in one line
what it could not do instead of failing."""

import os

from ..adapters.scip import INDEXERS, PythonScipIndexer, SandboxedPythonIndexer, ScipIndex, ScipOracle
from ..core.errors import BridgeError
from ..usecases.verify import LinkVerifier


class ScipCheck:
    def __init__(self, out_dir: str, report, sandbox: bool = False):
        self._dir = os.path.join(out_dir, 'scip')
        self._report = report
        self._sandbox = sandbox

    def verify(self, repos, links):
        """The links checked against the indexes that could be written; unchanged when none could."""
        indexes = {}
        for repo in repos:
            for path in self._index(repo):
                try:
                    indexes.setdefault(repo.name, []).append(ScipIndex.read(path))
                except BridgeError as e:
                    self._report(f'  scip      {repo.name}: skipped, {e}')
        if not indexes:
            self._report('  scip      no index written; links are not checked with SCIP')
            return links
        links = LinkVerifier(ScipOracle(indexes)).verify(links)
        c = LinkVerifier.count(links)
        self._report(
            f'  scip      {c["confirmed"]} links confirmed, {c["syntax"]} read from syntax alone, '
            f'{c["contradicted"]} contradicted, {c["unverified"]} unverified'
        )
        return links

    def _index(self, repo):
        os.makedirs(self._dir, exist_ok=True)
        written = []
        indexers = [i for i in (cls() for cls in self._indexers()) if i.applies(repo.path)]
        if not indexers:
            markers = ', '.join(sorted({m for cls in self._indexers() for m in cls.MARKERS}))
            self._report(f'  scip      {repo.name}: skipped, no project file at its root ({markers})')
        for indexer in indexers:
            try:
                written.append(indexer.index(repo.name, repo.path, self._dir))
            except BridgeError as e:  # no Node.js, no Docker, no rust-analyzer, or the indexer failed
                self._report(f'  scip      {repo.name} ({indexer.LANGUAGE}): skipped, {e}')
        return written

    def _indexers(self):
        if not self._sandbox:
            return INDEXERS
        return tuple(SandboxedPythonIndexer if cls is PythonScipIndexer else cls for cls in INDEXERS)
