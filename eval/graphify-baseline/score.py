"""Score Graphify's graphs against Atlas's link answer keys.

Graphify has no notion of an HTTP request or route, so the rule is generous: a key link counts as found when the graph
has any edge, of any relation and in either direction, between a node in a file that sends the request and a node in
the file that receives it (the route's file or its handler's file). Also counted: every edge that crosses from one
repository (or service folder) to another.

Usage: python3 eval/graphify-baseline/score.py <work folder from build.sh>
"""

import json
import os
import re
import sys
from collections import Counter

WORK = sys.argv[1] if len(sys.argv) > 1 else sys.exit('usage: score.py <work folder from build.sh>')
G, C = WORK, f'{WORK}/corpus'
A = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SOURCE_PATH = re.compile(r'[\w./-]+\.(?:py|rs|ts|tsx|js|jsx|go|java|rb|php)\b')


def load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def edges_by_file(graph, side_of):
    """{(side, file)} pairs for each edge's two ends, and a count of edges whose ends are on different sides."""
    where = {}
    for n in graph['nodes']:
        f = n.get('source_file')
        if f:
            where[n['id']] = side_of(n, os.path.normpath(f))
    pairs, crossing = set(where.values()), Counter()  # (side, file) alone: the file is in the graph
    for e in graph['links']:
        a, b = where.get(e['source']), where.get(e['target'])
        if not a or not b or a == b:
            continue
        pairs.add((a, b))
        pairs.add((b, a))
        if a[0] != b[0]:
            crossing[e.get('relation', '?')] += 1
    return pairs, crossing


COVERED = Counter()


def found(pairs, sends, receives):
    COVERED['links'] += 1
    COVERED['both files in graph'] += any(s in pairs for s in sends) and any(r in pairs for r in receives)
    return any((s, r) in pairs for s in sends for r in receives)


def merged_set(name, key_path):
    graph = load(f'{G}/{name}-merged.json')
    repo_of = repo_finder(graph)
    pairs, crossing = edges_by_file(graph, lambda n, f: (repo_of(n), f))
    key = load(key_path)
    links = [l for l in key['links'] if l['scope'] == 'prod']
    hits = []
    for l in links:
        sends = {(l['caller'], os.path.normpath(c['file'])) for c in l['call_sites']}
        files = {l['route']['file'], *SOURCE_PATH.findall(l['route'].get('handler', ''))}
        receives = {(l['target'], os.path.normpath(f)) for f in files}
        hits.append(found(pairs, sends, receives))
    return name, sum(hits), len(links), crossing


def repo_finder(graph):
    """The repository a merged node came from: merge-graphs tags it (field names vary by version)."""
    sample = graph['nodes'][0]
    for field in ('repo', '_repo', 'source_repo', 'repository'):
        if field in sample:
            return lambda n: n.get(field)
    raise SystemExit(f'no repo field on merged nodes: {sorted(sample)}')


def corpus_set(corpus, truth):
    graph = load(f'{C}/{corpus}/graphify-out/graph.json')
    folders = sorted(((os.path.normpath(f), s) for s, f in truth['services'].items()), key=lambda t: -len(t[0]))

    def side(n, f):
        for folder, service in folders:
            if folder == '.' or f == folder or f.startswith(folder + '/'):
                return service, f
        return '?', f

    pairs, crossing = edges_by_file(graph, side)
    hits = 0
    for l in truth['links']:
        def at(service, file):
            return service, os.path.normpath(os.path.join(truth['services'][service], file))
        sends = {at(l['caller'], s['file']) for s in l['send']}
        receive = l['receive'].get('file')  # none for a request to an outside host: no node can stand for it
        hits += found(pairs, sends, {at(l['target'], receive)} if receive else set())
    return hits, len(truth['links']), crossing


def main():
    rows = []
    for name in ('sentry', 'openedx'):
        n, hit, total, crossing = merged_set(name, f'{A}/eval/{name}/answer-key.json')
        rows.append((n, hit, total, sum(crossing.values()), dict(crossing)))
    for group, paths in (('devset', [f'{A}/eval/devset/{p}/TRUTH.json' for p in ('immich', 'plane', 'zulip')]),
                         ('apps', sorted(p for p in __import__('glob').glob(f'{A}/eval/tiny/apps/*/TRUTH.json'))),
                         ('apps2', sorted(p for p in __import__('glob').glob(f'{A}/eval/tiny/apps2/*/TRUTH.json')))):
        hit = total = 0
        crossing = Counter()
        for p in paths:
            app = os.path.basename(os.path.dirname(p))
            corpus = f'dev-{app}' if group == 'devset' else f'{group}-{app}'
            h, t, c = corpus_set(corpus, load(p))
            print(f'  {group:7} {app:14} {h}/{t}  crossing edges {sum(c.values())}')
            hit, total, crossing = hit + h, total + t, crossing + c
        rows.append((group, hit, total, sum(crossing.values()), dict(crossing)))
    print('\nset       Graphify finds   edges crossing a repository or service boundary')
    for name, hit, total, n, by in rows:
        print(f'{name:9} {hit:>3} / {total:<4}       {n}  {by}')
    print(f'\nsanity: {COVERED["both files in graph"]} of {COVERED["links"]} links have both their files in the graph')


if __name__ == '__main__':
    main()
