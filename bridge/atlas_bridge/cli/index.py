"""index: write SCIP indexes of repositories with each language's indexer, without running their code."""

import os

from ..adapters.scip import INDEXERS
from .command import Command
from .inputs import RepositoryInput


class IndexCommand(Command):
    name = 'index'
    help = 'write SCIP indexes for links --scip-dir (needs Node.js and/or rust-analyzer)'

    def configure(self, parser):
        parser.add_argument('repos', nargs='+', metavar='[name=]folder')
        parser.add_argument('-o', '--out-dir', default='scip', help='folder for <repo>.<language>.scip (default: scip)')

    def run(self, args):
        os.makedirs(args.out_dir, exist_ok=True)
        for repo in (RepositoryInput.parse(item).checked() for item in args.repos):
            indexers = [i for i in (cls() for cls in INDEXERS) if i.applies(repo.path)]
            if not indexers:
                self.report(f'{repo.name}: no indexer applies')
            for indexer in indexers:
                self.report(f'{repo.name}: {indexer.index(repo.name, repo.path, args.out_dir)}')
