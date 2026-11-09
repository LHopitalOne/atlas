"""links: HTTP links between repositories."""

from dataclasses import replace

from ..adapters.graphify import GraphifyLinkWriter
from ..adapters.linkfile import LinkFilePresenter
from ..adapters.scip import ScipCallGraph, ScipIndex, ScipOracle
from ..core.errors import LibraryIndexError
from ..core.http import Extraction
from ..usecases.hops import LibraryHops
from ..usecases.link import LinkFinder, LinkReport
from ..usecases.verify import LinkVerifier
from ..usecases.within import WithinRepoRule
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
        parser.add_argument(
            '--within',
            action='store_true',
            help="also link browser code to its own repository's server routes (a monorepo's frontend and backend)",
        )
        parser.add_argument(
            '--library',
            action='append',
            default=[],
            metavar='[name=]folder',
            help='a client library the services call (an SDK): its requests are reported at the service lines that '
            'call into it, found with the SCIP indexes (repeatable; needs --scip or --scip-dir)',
        )

    def run(self, args):
        from ..adapters.treesitter import TreeSitterExtractor  # needs the optional tree-sitter packages

        repos = [RepositoryInput.parse(item).checked() for item in args.repos]
        names = [r.name for r in repos]
        finder = LinkFinder(names, Aliases.parse(args.alias), args.include_tests, self._rules(args.within))
        extraction, extractor = Extraction(), TreeSitterExtractor()
        for repo in repos:
            extraction.extend(extractor.extract(repo.name, repo.path))
        indexes = self._indexes(args)
        extraction.calls += self._through_libraries(args, extractor, indexes)
        links = self._verified(finder.find(extraction), indexes)
        report = LinkReport(names, extraction, links)
        JsonFile.write(args.out, LinkFilePresenter().present(report), indent=1)
        found = sum(link.route is not None for link in report.links)
        self.report(f'{args.out}: {found} links, {len(report.links) - found} unmatched calls')
        if args.graphify_out:
            base = GraphifyLinkWriter(GraphInput.parse(args.graph).load() if args.graph else None)
            JsonFile.write(args.graphify_out, base.present(report.links))

    def _through_libraries(self, args, extractor, indexes):
        """The requests the --library repositories send, moved to the service lines that call into them."""
        libraries = [RepositoryInput.parse(item).checked() for item in args.library]
        if not libraries:
            return []
        if not indexes:
            raise LibraryIndexError([lib.name for lib in libraries])
        sent = Extraction()
        for lib in libraries:
            sent.extend(extractor.extract(lib.name, lib.path))
        names = {lib.name for lib in libraries}
        moved = LibraryHops(ScipCallGraph(indexes, names), names).calls(sent.calls)
        self.report(f'libraries: {len(moved)} requests reach the services through {", ".join(sorted(names))}')
        return [replace(call, test=extractor.is_test(call.file)) for call in moved]

    @staticmethod
    def _rules(within):
        """Within a repository, a frontend's own routes are asked about before a path is matched across repositories."""
        if not within:
            return LinkFinder.RULES
        *before, path_only = LinkFinder.RULES
        return (*before, WithinRepoRule, path_only)

    @staticmethod
    def _indexes(args):
        """{repo: [ScipIndex]} from --scip and --scip-dir."""
        inputs = [ScipInput.parse(item) for item in args.scip]
        if args.scip_dir:
            inputs += ScipInput.in_folder(args.scip_dir)
        indexes = {}
        for i in inputs:
            indexes.setdefault(i.name, []).append(ScipIndex.read(i.path))
        return indexes

    def _verified(self, links, indexes):
        """The links checked against the SCIP indexes, if any."""
        if not indexes:
            return links
        links = LinkVerifier(ScipOracle(indexes)).verify(links)
        counts = LinkVerifier.count(links)
        self.report(
            f'SCIP: {counts["confirmed"]} links confirmed, {counts["syntax"]} read from syntax alone, '
            f'{counts["contradicted"]} contradicted, {counts["unverified"]} unverified'
        )
        return links
