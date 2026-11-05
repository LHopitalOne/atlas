"""Command line and composition root.

  python -m atlas_bridge spec [options] [name=]graph.json ...    Graphify graphs to an Atlas spec
  python -m atlas_bridge links [options] [name=]repo-folder ...  HTTP links between repositories

Name an input with name=path; otherwise a graph is named after the folder that holds graphify-out/ (or the file's
stem) and a repository after its folder. This is the only module that reads or writes files.
"""

import argparse
import json
import os
import sys

from .adapters import atlas, graphify, linkfile
from .core.http import Extraction
from .core.model import CodeGraph
from .usecases.draw import GROUPINGS, draw
from .usecases.link import find_links


def input_name(path):
    path = os.path.abspath(path)
    parent = os.path.dirname(path)
    if os.path.basename(parent) == 'graphify-out':
        return os.path.basename(os.path.dirname(parent))
    return os.path.splitext(os.path.basename(path))[0]


def split_input(item):
    name, sep, path = item.partition('=')
    return (name, path) if sep else (input_name(item), item)


def write_json(path, data, indent=None):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=indent, separators=None if indent else (',', ':'))


def cmd_links(args):
    from .adapters.treesitter import TreeSitterExtractor  # needs the optional tree-sitter packages

    repos = dict(split_repo(item) for item in args.repos)
    aliases = dict(a.split('=', 1) for a in args.alias)
    extraction, extractor = Extraction(), TreeSitterExtractor()
    for name, root in repos.items():
        extraction.extend(extractor.extract(name, root))
    links = find_links(extraction, list(repos), aliases, include_tests=args.include_tests)
    write_json(args.out, linkfile.present(links, extraction, list(repos)), indent=1)
    found = sum(link.route is not None for link in links)
    print(f'{args.out}: {found} links, {len(links) - found} unmatched calls', file=sys.stderr)
    if args.graphify_out:
        base = None
        if args.graph:
            with open(args.graph, encoding='utf-8') as f:
                base = json.load(f)
        write_json(args.graphify_out, graphify.with_links(base, links))


def split_repo(item):
    name, sep, path = item.partition('=')
    return (name, path) if sep else (os.path.basename(os.path.abspath(item)), item)


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
    k = sub.add_parser('links', help='find HTTP links between repositories (needs atlas-bridge[links])')
    k.add_argument('repos', nargs='+', metavar='[name=]folder')
    k.add_argument('-o', '--out', default='links.json', help='links as JSON (default: links.json)')
    k.add_argument(
        '--alias',
        action='append',
        default=[],
        metavar='word=repo',
        help='a word in client code that means a repository, e.g. upstream=sentry (repeatable)',
    )
    k.add_argument('--include-tests', action='store_true', help='also link requests made only by tests and tooling')
    k.add_argument('--graph', help='a Graphify graph of the same repositories (from graphify merge-graphs)')
    k.add_argument('--graphify-out', help='write the Graphify graph (or a new one) with the links added')
    k.set_defaults(run=cmd_links)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    args.run(args)


if __name__ == '__main__':
    main()
