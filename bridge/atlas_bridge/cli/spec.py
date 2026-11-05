"""spec: Graphify graphs to an Atlas graph spec."""

import json
import sys

from ..adapters.atlas import AtlasSpecPresenter
from ..adapters.graphify import GraphifyReader
from ..core.model import CodeGraph
from ..usecases.draw import GROUPINGS, MapDrawer
from .command import Command
from .inputs import GraphInput, JsonFile


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

    def run(self, args):
        graph = CodeGraph()
        reader = GraphifyReader(graph)
        for item in args.graphs:
            g = GraphInput.parse(item)
            reader.read(g.load(), g.name, source=g.path)
        spec = AtlasSpecPresenter(args.title).present(MapDrawer(GROUPINGS[args.group]).draw(graph))
        if args.out == '-':
            sys.stdout.write(json.dumps(spec, separators=(',', ':')))
            return
        JsonFile.write(args.out, spec)
        services = [s for r in spec['repos'] for d in r['domains'] for s in d['services']]
        leaves = sum(len(s['leaves']) for s in services)
        self.report(
            f'{args.out}: {len(spec["repos"])} repos, {len(services)} files, {leaves} symbols, '
            f'{len(spec["edges"])} links'
        )
