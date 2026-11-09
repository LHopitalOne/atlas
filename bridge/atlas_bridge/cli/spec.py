"""spec: Graphify graphs (and, optionally, the HTTP links between their repositories) to an Atlas graph spec."""

import json
import sys

from ..adapters.atlas import AtlasSpecPresenter, CodeSource, HttpLayer, LinkFile
from ..adapters.graphify import GraphifyReader
from ..core.errors import LinkFormatError
from ..core.model import CodeGraph
from ..usecases.draw import GROUPINGS, MapDrawer
from .command import Command
from .inputs import GraphInput, JsonFile, RepositoryInput


class SpecCommand(Command):
    name = 'spec'
    help = 'write an Atlas graph spec from one or more graph.json files'

    def configure(self, parser):
        parser.add_argument('graphs', nargs='+', metavar='[name=]graph.json')
        parser.add_argument('-o', '--out', default='-', help='output file (default: stdout)')
        parser.add_argument(
            '--group',
            choices=sorted(GROUPINGS),
            default='community',
            help="what becomes a domain: Graphify's communities (default) or folders",
        )
        parser.add_argument('--title', default='Graphify graph')
        parser.add_argument('--links', help='the links JSON the links command wrote: HTTP links, with their proof')
        parser.add_argument(
            '--repo',
            action='append',
            default=[],
            metavar='name=folder',
            help='where a repository is checked out, to embed the lines each link cites and link them on GitHub',
        )
        parser.add_argument('--accuracy', help='a JSON object shown with the links: how they scored on an answer key')

    def run(self, args):
        graph = CodeGraph()
        reader = GraphifyReader(graph)
        for item in args.graphs:
            g = GraphInput.parse(item)
            reader.read(g.load(), g.name, source=g.path)
        http = self._http(args)
        if http is not None:
            http.add_files(graph)
        spec = AtlasSpecPresenter(args.title, http).present(MapDrawer(GROUPINGS[args.group]).draw(graph))
        if args.out == '-':
            sys.stdout.write(json.dumps(spec, separators=(',', ':')))
            return
        JsonFile.write(args.out, spec)
        services = [s for r in spec['repos'] for d in r['domains'] for s in d['services']]
        leaves = sum(len(s['leaves']) for s in services)
        http_note = f', {len(spec["links"])} HTTP links' if 'links' in spec else ''
        self.report(
            f'{args.out}: {len(spec["repos"])} repos, {len(services)} files, {leaves} symbols, '
            f'{len(spec["edges"])} links{http_note}'
        )

    @staticmethod
    def _http(args):
        if not args.links:
            return None
        records = LinkFile(args.links).parse(JsonFile.read(args.links))
        folders = {r.name: r.path for r in (RepositoryInput.parse(item).checked() for item in args.repo)}
        accuracy = JsonFile.read(args.accuracy) if args.accuracy else None
        if accuracy is not None and not isinstance(accuracy, dict):
            raise LinkFormatError(args.accuracy, 'the accuracy file must hold one JSON object')
        return HttpLayer(records, CodeSource(folders), accuracy)
