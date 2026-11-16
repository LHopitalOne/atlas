"""index: write SCIP indexes of repositories with each language's indexer, without running their code."""

import os

from ..adapters.scip import INDEXERS, PythonScipIndexer, SandboxedPythonIndexer
from ..core.errors import IndexerFailedError, IndexerUnavailableError, IndexingIncompleteError
from .command import Command
from .inputs import RepositoryInput


class IndexCommand(Command):
    name = 'index'
    help = 'write SCIP indexes for links --scip-dir (needs Node.js and/or rust-analyzer)'

    def configure(self, parser):
        parser.add_argument('repos', nargs='+', metavar='[name=]folder')
        parser.add_argument('-o', '--out-dir', default='scip', help='folder for <repo>.<language>.scip (default: scip)')
        parser.add_argument(
            '--sandbox',
            action='store_true',
            help='index Python in a Docker container with the libraries the repository declares installed there, so '
            'calls into them resolve (needs Docker)',
        )

    def run(self, args):
        """Every index that can be written is: a failing indexer is reported and the run goes on; the run then fails
        naming what was not written."""
        os.makedirs(args.out_dir, exist_ok=True)
        repos = [RepositoryInput.parse(item).checked() for item in args.repos]
        failed = []
        for repo in repos:
            indexers = [i for i in (cls() for cls in self._indexers(args.sandbox)) if i.applies(repo.path)]
            if not indexers:
                self.report(f'{repo.name}: no indexer applies')
            for indexer in indexers:
                try:
                    self.report(f'{repo.name}: {indexer.index(repo.name, repo.path, args.out_dir)}')
                except (IndexerFailedError, IndexerUnavailableError) as e:
                    self.report(f'{repo.name}: skipped {indexer.LANGUAGE}, {e}')
                    failed.append(f'{repo.name} ({indexer.LANGUAGE})')
        if failed:
            raise IndexingIncompleteError(failed)

    @staticmethod
    def _indexers(sandbox):
        if not sandbox:
            return INDEXERS
        return tuple(SandboxedPythonIndexer if cls is PythonScipIndexer else cls for cls in INDEXERS)
