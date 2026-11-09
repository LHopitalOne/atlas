"""map: repositories in, the Atlas page out, in one command (also installed as `atlas`)."""

import os
import time
import webbrowser

from ..usecases.draw import GROUPINGS
from .command import Command
from .inputs import Aliases, RepositoryInput
from .pipeline import MapPipeline


class MapCommand(Command):
    name = 'map'
    help = 'map repositories with Graphify, find the HTTP links between them and open the Atlas page'

    def configure(self, parser):
        parser.add_argument('repos', nargs='+', metavar='[name=]folder', help='repository folders')
        parser.add_argument('-o', '--out-dir', default='atlas-out', help='output folder (default: atlas-out)')
        parser.add_argument('--refresh', action='store_true', help='run Graphify again even if graphify-out/ exists')
        parser.add_argument(
            '--verify', action='store_true', help='confirm links with SCIP indexes (needs Node.js and/or rust-analyzer)'
        )
        parser.add_argument('--sandbox', action='store_true', help='with --verify, index Python in Docker')
        parser.add_argument(
            '--alias',
            action='append',
            default=[],
            metavar='word=repo',
            help='a word in client code that means a repository, e.g. upstream=sentry (repeatable)',
        )
        parser.add_argument('--include-tests', action='store_true', help='also link requests made only by tests')
        parser.add_argument(
            '--group', choices=sorted(GROUPINGS), default='community', help='what becomes a domain (default: community)'
        )
        parser.add_argument('--title', help='the map title (default: the repository names)')
        parser.add_argument(
            '--graph-json', action='store_true', help='write graph.json even for very large graphs (over 200,000 nodes)'
        )
        parser.add_argument('--no-open', action='store_true', help='write the page without opening a browser')

    def run(self, args):
        start = time.monotonic()
        repos = self.unique([RepositoryInput.parse(item).checked() for item in args.repos])
        args.aliases = Aliases.parse(args.alias)
        args.title = args.title or ', '.join(r.name for r in repos)
        self.report(f'atlas: mapping {args.title}')
        page = MapPipeline(args, self.report).run(repos)
        self.report(f'atlas: wrote {page} in {time.monotonic() - start:.0f}s')
        if args.no_open or not self.open(page):
            self.report(f'atlas: open {page} in a browser')

    @staticmethod
    def unique(repos):
        """The repositories, renamed 'name-2', 'name-3' when two folders share a name."""
        seen, out = {}, []
        for r in repos:
            seen[r.name] = seen.get(r.name, 0) + 1
            out.append(r if seen[r.name] == 1 else RepositoryInput(f'{r.name}-{seen[r.name]}', r.path))
        return out

    @staticmethod
    def open(page):
        try:
            return webbrowser.open('file://' + os.path.abspath(page))
        except webbrowser.Error:
            return False
