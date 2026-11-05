"""Command line: python -m atlas_bridge spec [options] [name=]graph.json ...

Each input is a Graphify graph.json. Name it with name=path; otherwise the name is the folder that holds
graphify-out/, or the file's stem.
"""
import argparse
import json
import os
import sys

from .spec import SpecBuilder


def input_name(path):
    path = os.path.abspath(path)
    parent = os.path.dirname(path)
    if os.path.basename(parent) == 'graphify-out':
        return os.path.basename(os.path.dirname(parent))
    return os.path.splitext(os.path.basename(path))[0]


def cmd_spec(args):
    builder = SpecBuilder(group=args.group)
    for item in args.graphs:
        name, _, path = item.rpartition('=') if '=' in item else ('', '', item)
        with open(path, encoding='utf-8') as f:
            builder.add(json.load(f), name or input_name(path))
    spec = builder.build(title=args.title)
    out = json.dumps(spec, separators=(',', ':'))
    if args.out == '-':
        sys.stdout.write(out)
    else:
        with open(args.out, 'w', encoding='utf-8') as f: f.write(out)
        services = sum(len(d['services']) for r in spec['repos'] for d in r['domains'])
        leaves = sum(len(s['leaves']) for r in spec['repos'] for d in r['domains'] for s in d['services'])
        print(f'{args.out}: {len(spec["repos"])} repos, {services} files, {leaves} symbols, {len(spec["edges"])} links',
              file=sys.stderr)


def main(argv=None):
    p = argparse.ArgumentParser(prog='atlas_bridge', description='Graphify graph.json to Atlas.')
    sub = p.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('spec', help='write an Atlas graph spec from one or more graph.json files')
    s.add_argument('graphs', nargs='+', metavar='[name=]graph.json')
    s.add_argument('-o', '--out', default='-', help='output file (default: stdout)')
    s.add_argument('--group', choices=['community', 'folder'], default='community',
                   help="what becomes a domain: Graphify's communities (default) or folders")
    s.add_argument('--title', default='Graphify graph')
    s.set_defaults(run=cmd_spec)
    args = p.parse_args(argv)
    args.run(args)


if __name__ == '__main__':
    main()
