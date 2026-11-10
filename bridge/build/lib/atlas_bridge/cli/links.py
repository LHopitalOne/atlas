"""links: HTTP links between repositories."""

from ..adapters.graphify import GraphifyLinkWriter
from ..adapters.linkfile import LinkFilePresenter
from ..adapters.scip import ScipIndex, ScipOracle
from ..core.http import Extraction
from ..usecases.link import LinkFinder, LinkReport
from ..usecases.verify import LinkVerifier
from .command import Command
from .inputs import Aliases, GraphInput, JsonFile, RepositoryInput, ScipInput


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
        parser.add_argument(
            '--scip',
            action='append',
            default=[],
            metavar='[repo=]index.scip',
            help='a SCIP index of a repository, to confirm what each link rests on (repeatable)',
        )
        parser.add_argument(
            '--scip-dir', help='a folder of <repo>[.<language>].scip files, as the index command writes'
        )

    def run(self, args):
        from ..adapters.treesitter import TreeSitterExtractor  # needs the optional tree-sitter packages

        repos = [RepositoryInput.parse(item).checked() for item in args.repos]
        names = [r.name for r in repos]
        finder = LinkFinder(names, Aliases.parse(args.alias), include_tests=args.include_tests)
        extraction, extractor = Extraction(), TreeSitterExtractor()
        for repo in repos:
            extraction.extend(extractor.extract(repo.name, repo.path))
        links = self._verified(finder.find(extraction), args)
        report = LinkReport(names, extraction, links)
        JsonFile.write(args.out, LinkFilePresenter().present(report), indent=1)
        found = sum(link.route is not None for link in report.links)
        self.report(f'{args.out}: {found} links, {len(report.links) - found} unmatched calls')
        if args.graphify_out:
            base = GraphInput.parse(args.graph).load() if args.graph else None
            JsonFile.write(args.graphify_out, GraphifyLinkWriter(base).present(report.links))

    def _verified(self, links, args):
        """The links checked against the SCIP indexes given, if any."""
        inputs = [ScipInput.parse(item) for item in args.scip]
        if args.scip_dir:
            inputs += ScipInput.in_folder(args.scip_dir)
        if not inputs:
            return links
        indexes = {}
        for i in inputs:
            indexes.setdefault(i.name, []).append(ScipIndex.read(i.path))
        links = LinkVerifier(ScipOracle(indexes)).verify(links)
        counts = LinkVerifier.count(links)
        self.report(
            f'SCIP: {counts["confirmed"]} links confirmed, {counts["syntax"]} read from syntax alone, '
            f'{counts["contradicted"]} contradicted, {counts["unverified"]} unverified'
        )
        return links
