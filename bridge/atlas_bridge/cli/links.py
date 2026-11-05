"""links: HTTP links between repositories."""

from ..adapters.graphify import GraphifyLinkWriter
from ..adapters.linkfile import LinkFilePresenter
from ..core.http import Extraction
from ..usecases.link import LinkFinder, LinkReport
from .command import Command
from .inputs import Aliases, GraphInput, JsonFile, RepositoryInput


class LinksCommand(Command):
    name = 'links'
    help = 'find HTTP links between repositories (needs atlas-bridge[links])'

    def configure(self, parser):
        parser.add_argument('repos', nargs='+', metavar='[name=]folder')
        parser.add_argument('-o', '--out', default='links.json', help='links as JSON (default: links.json)')
        parser.add_argument(
            '--alias',
            action='append',
            default=[],
            metavar='word=repo',
            help='a word in client code that means a repository, e.g. upstream=sentry (repeatable)',
        )
        parser.add_argument(
            '--include-tests', action='store_true', help='also link requests made only by tests and tooling'
        )
        parser.add_argument('--graph', help='a Graphify graph of the same repositories (from graphify merge-graphs)')
        parser.add_argument('--graphify-out', help='write the Graphify graph (or a new one) with the links added')

    def run(self, args):
        from ..adapters.treesitter import TreeSitterExtractor  # needs the optional tree-sitter packages

        repos = [RepositoryInput.parse(item).checked() for item in args.repos]
        names = [r.name for r in repos]
        finder = LinkFinder(names, Aliases.parse(args.alias), include_tests=args.include_tests)
        extraction, extractor = Extraction(), TreeSitterExtractor()
        for repo in repos:
            extraction.extend(extractor.extract(repo.name, repo.path))
        report = LinkReport(names, extraction, finder.find(extraction))
        JsonFile.write(args.out, LinkFilePresenter().present(report), indent=1)
        found = sum(link.route is not None for link in report.links)
        self.report(f'{args.out}: {found} links, {len(report.links) - found} unmatched calls')
        if args.graphify_out:
            base = GraphInput.parse(args.graph).load() if args.graph else None
            JsonFile.write(args.graphify_out, GraphifyLinkWriter(base).present(report.links))
