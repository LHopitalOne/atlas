"""map: repositories in, the Atlas page out, in one command (also installed as `atlas`)."""

import argparse
import os
import time
import webbrowser

from ..usecases.draw import GROUPINGS
from .command import Command
from .inputs import Aliases, RepositoryInput
from .pipeline import MapPipeline
from .serve import MapServer


class MapCommand(Command):
    name = 'map'
    help = 'map repositories with Graphify, find the HTTP links between them and open the Atlas page'

    def configure(self, parser):
        parser.add_argument('repos', nargs='+', metavar='[name=]folder', help='repository folders')
        parser.add_argument('-o', '--out-dir', default='atlas-out', help='output folder (default: atlas-out)')
        parser.add_argument('--refresh', action='store_true', help='run Graphify again even if graphify-out/ exists')
        parser.add_argument(
            '--no-scip',
            dest='scip',
            action='store_false',
            help='do not index with SCIP (by default each repository is indexed where an indexer runs: Node.js for '
            'Python and TypeScript, rust-analyzer for Rust; the index checks the links and adds the edges it sees)',
        )
        parser.add_argument('--verify', action='store_true', help=argparse.SUPPRESS)  # SCIP is on by default now
        parser.add_argument('--sandbox', action='store_true', help='index Python with SCIP in Docker')
        parser.add_argument(
            '--alias',
            action='append',
            default=[],
            metavar='word=repo',
            help='a word in client code that means a repository, e.g. upstream=sentry (repeatable)',
        )
        parser.add_argument(
            '--no-within',
            dest='within',
            action='store_false',
            help="do not link a repository's browser code to its own server routes",
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
        parser.add_argument(
            '--no-ask-key',
            dest='ask_key',
            action='store_false',
            help='leave OPENROUTER_API_KEY out of atlas.html (by default it is written in so Ask Atlas works by '
            'opening the file; without it Ask is off unless --serve shows the map)',
        )
        parser.add_argument(
            '--serve',
            action='store_true',
            help='show the map from a local server (Ask then reaches OpenRouter with OPENROUTER_API_KEY) until Ctrl+C',
        )
        self._models(parser)

    @staticmethod
    def _models(parser):
        """The options that ask a model on OpenRouter (needs OPENROUTER_API_KEY)."""
        parser.add_argument(
            '--jev',
            action='store_true',
            help='let Jev (a decision model on OpenRouter; needs OPENROUTER_API_KEY) choose among the routes the code '
            'leaves open for a request; its picks are marked "Chosen by Jev"',
        )
        parser.add_argument(
            '--read',
            action='store_true',
            help='let a small model (meta/muse-ember on OpenRouter; needs OPENROUTER_API_KEY) read the files the code '
            'reading leaves unexplained for the requests and routes they hold; the code checks each claim, and links '
            'found so are marked "Read by AI"',
        )
        parser.add_argument(
            '--enrich',
            action='store_true',
            help='let a small model (meta/muse-ember on OpenRouter; needs OPENROUTER_API_KEY) say in one sentence what '
            'each file does, with its role and tags; shown as AI summaries',
        )

    def run(self, args):
        start = time.monotonic()
        repos = self.unique([RepositoryInput.parse(item).checked() for item in args.repos])
        args.aliases = Aliases.parse(args.alias)
        args.title = args.title or ', '.join(r.name for r in repos)
        self.report(f'atlas: mapping {args.title}')
        page = MapPipeline(args, self.report).run(repos)
        self.report(f'atlas: wrote {page} in {time.monotonic() - start:.0f}s')
        if args.serve:
            MapServer(os.path.dirname(os.path.abspath(page)), 0).run(
                os.path.basename(page), not args.no_open, self.report
            )
            return
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
