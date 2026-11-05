"""Command line and composition root: python -m atlas_bridge spec [options] [name=]graph.json ...

Each input is a Graphify graph.json. Name it with name=path; otherwise the name is the folder that holds
graphify-out/, or the file's stem. This is the only module that reads or writes files.
"""

import argparse
import json
import os
import sys

from .adapters import atlas, graphify
from .core.model import CodeGraph
from .usecases.draw import GROUPINGS, draw


def input_name(path):
    path = os.path.abspath(path)
    parent = os.path.dirname(path)
    if os.path.basename(parent) == 'graphify-out':
        return os.path.basename(os.path.dirname(parent))
    return os.path.splitext(os.path.basename(path))[0]


def split_input(item):
    name, sep, path = item.partition('=')
    return (name, path) if sep else (input_name(item), item)


def cmd_spec(args):
    graph = CodeGraph()
    for item in args.graphs:
        name, path = split_input(item)
        with open(path, encoding='utf-8') as f:
            graphify.read(graph, json.load(f), name)
    spec = atlas.present(draw(graph, GROUPINGS[args.group]), title=args.title)
    text = json.dumps(spec, separators=(',', ':'))
    if args.out == '-':
        sys.stdout.write(text)
        return
    with open(args.out, 'w', encoding='utf-8') as f:
        f.write(text)
    services = [s for r in spec['repos'] for d in r['domains'] for s in d['services']]
    leaves = sum(len(s['leaves']) for s in services)
    print(
        f'{args.out}: {len(spec["repos"])} repos, {len(services)} files, {leaves} symbols, {len(spec["edges"])} links',
        file=sys.stderr,
    )


def parser():
    p = argparse.ArgumentParser(prog='atlas_bridge', description='Graphify graph.json to Atlas.')
    sub = p.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('spec', help='write an Atlas graph spec from one or more graph.json files')
    s.add_argument('graphs', nargs='+', metavar='[name=]graph.json')
    s.add_argument('-o', '--out', default='-', help='output file (default: stdout)')
    s.add_argument(
        '--group',
        choices=sorted(GROUPINGS),
        default='community',
        help="what becomes a domain: Graphify's communities (default) or folders",
    )
    s.add_argument('--title', default='Graphify graph')
    s.set_defaults(run=cmd_spec)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    args.run(args)


if __name__ == '__main__':
    main()
