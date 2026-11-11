"""The SCIP step of the map command: index each repository it can (reusing an index while the code is unchanged),
verify the links, and say in one line what it could not do instead of failing."""

import hashlib
import os
import subprocess

from ..adapters.scip import INDEXERS, PythonScipIndexer, SandboxedPythonIndexer, ScipIndex, ScipOracle, ScipReferences
from ..core.errors import BridgeError
from ..usecases.scipedges import ScipEdges
from ..usecases.verify import LinkVerifier


class ScipPass:
    """Adds to a code graph the edges the SCIP indexes show, and says what it did in one line."""

    def __init__(self, report):
        self._report = report

    def run(self, graph, indexes):
        edges = ScipEdges(ScipReferences(indexes))
        edges.add(graph)
        r = edges.report
        self._report(
            f"  scip      {r.files:,} files read: {r.checked:,} of the graph's edges seen by SCIP, {r.added:,} edges "
            f'added, {r.unseen_guesses:,} guessed edges SCIP does not show'
        )
        return graph


class ScipCheck:
    STAMP = '.stamp'  # next to an index: the commit and changes it was written for
    HEAD = ['git', 'rev-parse', 'HEAD']
    # uncommitted changes to the code: not Graphify's output, which is not code
    CHANGES = ['git', 'status', '--porcelain', '--', '.', ':(exclude)graphify-out', ':(exclude)**/graphify-out']

    def __init__(self, out_dir: str, report, sandbox: bool = False, refresh: bool = False):
        self._dir = os.path.join(out_dir, 'scip')
        self._report = report
        self._sandbox = sandbox
        self._refresh = refresh

    def index(self, repos) -> dict:
        """{repo: [ScipIndex]} for the repositories an indexer could index; {} when none could."""
        indexes = {}
        for repo in repos:
            for path in self._index(repo):
                try:
                    indexes.setdefault(repo.name, []).append(ScipIndex.read(path))
                except BridgeError as e:
                    self._report(f'  scip      {repo.name}: skipped, {e}')
        if not indexes:
            self._report('  scip      no index written; links and edges are not checked with SCIP')
        return indexes

    def verify(self, links, indexes):
        """The links checked against the indexes; unchanged when there are none."""
        if not indexes:
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
        state = self._state(repo.path)
        for indexer in indexers:
            out = os.path.join(self._dir, f'{repo.name}.{indexer.LANGUAGE}.scip')
            if state and not self._refresh and self._stamped(out) == state:
                self._report(f'  scip      {repo.name} ({indexer.LANGUAGE}): unchanged, index reused')
                written.append(out)
                continue
            try:
                self._report(f'  scip      {repo.name} ({indexer.LANGUAGE}): indexing ...')
                written.append(indexer.index(repo.name, repo.path, self._dir))
                self._stamp(out, state)
            except BridgeError as e:  # no Node.js, no Docker, no rust-analyzer, or the indexer failed
                self._report(f'  scip      {repo.name} ({indexer.LANGUAGE}): skipped, {e}')
        return written

    def _state(self, root):
        """The repository's commit and a digest of its uncommitted changes; '' outside git."""
        changes = list(self.CHANGES)
        inside = os.path.relpath(os.path.abspath(self._dir), os.path.abspath(root))
        if not inside.startswith('..'):
            changes.append(f':(exclude){inside}')  # the indexes this step writes are not a change to the code
        try:
            outs = [subprocess.run(c, cwd=root, capture_output=True, check=True).stdout for c in (self.HEAD, changes)]
        except (OSError, subprocess.CalledProcessError):
            return ''
        return outs[0].decode().strip() + ':' + hashlib.sha256(outs[1]).hexdigest()

    def _stamped(self, out):
        try:
            with open(out + self.STAMP, encoding='utf-8') as f:
                return f.read() if os.path.exists(out) else ''
        except OSError:
            return ''

    def _stamp(self, out, state):
        if state:
            with open(out + self.STAMP, 'w', encoding='utf-8') as f:
                f.write(state)

    def _indexers(self):
        if not self._sandbox:
            return INDEXERS
        return tuple(SandboxedPythonIndexer if cls is PythonScipIndexer else cls for cls in INDEXERS)
