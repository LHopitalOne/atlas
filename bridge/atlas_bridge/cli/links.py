"""links: HTTP links between repositories."""

from dataclasses import replace

from ..adapters.graphify import GraphifyLinkWriter
from ..adapters.linkfile import LinkFilePresenter
from ..adapters.muse import MuseReader
from ..adapters.scip import ScipCallGraph, ScipIndex, ScipOracle
from ..core.errors import LibraryIndexError
from ..core.http import Extraction
from ..core.model import Status
from ..usecases.channels import OwnChannelRule
from ..usecases.hops import LibraryHops
from ..usecases.link import LinkFinder, LinkReport
from ..usecases.mentions import NamedChannels
from ..usecases.outside import OutsideRule
from ..usecases.verify import LinkVerifier
from ..usecases.within import NoRouteRule, WithinRepoRule
from .command import Command
from .inputs import Aliases, GraphInput, JsonFile, RepositoryInput, ScipInput
from .judge import JudgePass
from .read import ReadOptions, ReadPass


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
            '--no-scip-search',
            action='store_true',
            help='with SCIP indexes, still read requests and their callers by name only (the indexes then only verify)',
        )
        parser.add_argument(
            '--within',
            action='store_true',
            help="also link browser code to its own repository's server routes (a monorepo's frontend and backend)",
        )
        self._models(parser)
        parser.add_argument(
            '--library',
            action='append',
            default=[],
            metavar='[name=]folder',
            help='a client library the services call (an SDK): its requests are reported at the service lines that '
            'call into it, found with the SCIP indexes (repeatable; needs --scip or --scip-dir)',
        )

    @staticmethod
    def _models(parser):
        """The options that ask a model on OpenRouter (needs OPENROUTER_API_KEY)."""
        parser.add_argument(
            '--jev',
            action='store_true',
            help='let Jev (a decision model on OpenRouter; needs OPENROUTER_API_KEY) choose among the routes the code '
            'leaves open for a request; its picks are marked judged',
        )
        parser.add_argument(
            '--read',
            action='store_true',
            help='let a language model on OpenRouter (needs OPENROUTER_API_KEY) read the files the extractors leave '
            'unexplained for the requests they send; the code checks each claim, and links found so are marked read',
        )
        parser.add_argument('--read-model', help=f'the model --read asks (default: {MuseReader.MODEL})')

    def run(self, args):
        from ..adapters.treesitter import FileMentions, TreeSitterExtractor  # needs the optional tree-sitter packages

        repos = [RepositoryInput.parse(item).checked() for item in args.repos]
        libraries = [RepositoryInput.parse(item).checked() for item in args.library]
        names = [r.name for r in repos]
        indexes = self._indexes(args)
        graph = ScipCallGraph(indexes, {lib.name for lib in libraries}) if indexes else None
        extractor = TreeSitterExtractor(None if args.no_scip_search else graph)
        finder = LinkFinder(
            names, Aliases.parse(args.alias), args.include_tests, self._rules(args.within), self._fallbacks(args.within)
        )
        extraction = Extraction()
        for repo in repos:
            extraction.extend(extractor.extract(repo.name, repo.path))
        extraction.calls += self._through_libraries(libraries, extractor, graph)
        named = NamedChannels(FileMentions({r.name: r.path for r in repos}), names)
        extraction.routes += named.routes(extraction.calls, extraction.routes)
        links = finder.find(extraction)
        if args.read:
            folders = {r.name: r.path for r in repos}
            options = ReadOptions(
                Aliases.parse(args.alias), args.include_tests, args.within, extractor.is_test, args.read_model
            )
            links = ReadPass(self.report).run(links, extraction, folders, options)
        if args.jev:
            folders = {r.name: r.path for r in repos}
            links = JudgePass(self.report).run(links, extraction, folders, args.include_tests, args.within)
        links = self._verified(links, indexes)
        report = LinkReport(names, extraction, links)
        JsonFile.write(args.out, LinkFilePresenter().present(report), indent=1)
        found = sum(link.route is not None for link in report.links)
        outside = sum(link.status == Status.OUTSIDE for link in report.links)
        no_route = len(report.links) - found - outside
        self.report(f'{args.out}: {found} links, {outside} to outside services, {no_route} with no route')
        if args.graphify_out:
            base = GraphifyLinkWriter(GraphInput.parse(args.graph).load() if args.graph else None)
            JsonFile.write(args.graphify_out, base.present(report.links))

    def _through_libraries(self, libraries, extractor, graph):
        """The requests the --library repositories send, moved to the service lines that call into them."""
        if not libraries:
            return []
        if graph is None:
            raise LibraryIndexError([lib.name for lib in libraries])
        sent = Extraction()
        for lib in libraries:
            sent.extend(extractor.extract(lib.name, lib.path))
        names = {lib.name for lib in libraries}
        moved = LibraryHops(graph, names).calls(sent.calls)
        self.report(f'libraries: {len(moved)} requests reach the services through {", ".join(sorted(names))}')
        return [replace(call, test=extractor.is_test(call.file)) for call in moved]

    @staticmethod
    def _rules(within):
        """Before a channel is matched across repositories: a task or work queue its own repository handles, and
        (with --within) browser code calling its own server."""
        *before, path_only = LinkFinder.RULES
        mine = (OwnChannelRule, WithinRepoRule) if within else (OwnChannelRule,)
        return (*before, *mine, path_only)

    @staticmethod
    def _fallbacks(within):
        """For a call nothing links: a request that leaves the repositories, and (with --within) browser code calling
        a route its own server does not have."""
        return (OutsideRule, NoRouteRule) if within else (OutsideRule,)

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
