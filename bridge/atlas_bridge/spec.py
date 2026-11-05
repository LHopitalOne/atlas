"""Turn Graphify graph.json files into an Atlas graph spec (docs/GRAPH_SPEC.md).

Mapping:
  repo     the input's name, or each node's `repo` (graphs combined with `graphify merge-graphs`)
  domain   the Graphify community most of the file's nodes belong to (or the file's folder, with group='folder')
  service  a source file
  leaf     a symbol in that file: 1 function, 2 class, 3 anything else (constants, doc sections)

Edge status follows Graphify's confidence: EXTRACTED -> 0 Matched, AMBIGUOUS -> 1, INFERRED -> 3.
Structural relations (a file contains its symbols, a class its methods) are the hierarchy itself, not edges.
"""
import os
import re
from collections import Counter, defaultdict

STRUCTURAL = {'contains', 'method', 'rationale_for'}
STATUS = {'EXTRACTED': 0, 'AMBIGUOUS': 1, 'INFERRED': 3}
CERTAINTY = {0: 0, 3: 1, 1: 2, 2: 3}  # when two edges join the same pair, keep the more certain one
SKIP_TYPES = {'rationale'}  # comment nodes: their text already sits next to the symbol they explain


def line_of(node):
    m = re.match(r'L(\d+)', node.get('source_location') or '')
    return int(m.group(1)) if m else 0


def is_file_node(node):
    src = node.get('source_file') or ''
    return bool(src) and not node.get('_callable') and node.get('label') == os.path.basename(src)


def leaf_kind(node):
    if node.get('_callable_class'): return 2
    if node.get('_callable'): return 1
    return 3


def domain_name(nodes, group):
    if group == 'folder':
        return os.path.dirname(nodes[0]['source_file']) or '(root)'
    votes = Counter((n.get('community', -1), n.get('community_name') or '') for n in nodes)
    (cid, cname), _ = min(votes.items(), key=lambda kv: (-kv[1], kv[0][0]))
    return cname or f'Community {cid}'


def unique(names):
    """Same-named items get ' (2)', ' (3)' so every name in a group is distinct."""
    seen, out = Counter(), []
    for n in names:
        seen[n] += 1
        out.append(n if seen[n] == 1 else f'{n} ({seen[n]})')
    return out


class SpecBuilder:
    """Collects files and symbols from one or more Graphify graphs, then lays them out as an Atlas spec."""

    def __init__(self, group='community'):
        self.group = group
        self.files = defaultdict(list)  # (repo, source_file) -> nodes in that file
        self.node_file = {}             # node key -> (repo, source_file)
        self.edges = []                 # (source key, target key, status)
        self.versions = set()

    def add(self, graph, repo):
        """Add one graph.json (already parsed). `repo` names it unless its nodes carry their own `repo`."""
        self.versions.add((graph.get('graph') or {}).get('graphify_version'))
        keys = {}
        for n in graph['nodes']:
            src = n.get('source_file')
            if not src or n.get('file_type') in SKIP_TYPES: continue
            key = (n.get('repo') or repo, n['id'])
            keys[n['id']] = key
            self.node_file[key] = (key[0], src)
            self.files[(key[0], src)].append(n)
        for e in graph.get('links') or graph.get('edges') or []:
            if e.get('relation') in STRUCTURAL: continue
            a, b = keys.get(e['source']), keys.get(e['target'])
            if a and b and a != b:
                self.edges.append((a, b, STATUS.get(e.get('confidence'), 3)))

    def build(self, title='Graphify graph'):
        tree = defaultdict(lambda: defaultdict(list))  # repo -> domain -> [(source_file, nodes)]
        for (repo, src), nodes in self.files.items():
            tree[repo][domain_name(nodes, self.group)].append((src, nodes))
        repos, order = [], []  # order: per service, (file key, [leaf node keys]) in id order
        for repo in sorted(tree):
            domains = []
            for dom in sorted(tree[repo]):
                files = sorted(tree[repo][dom])
                services = []
                for (src, nodes), name in zip(files, unique([os.path.basename(s) for s, _ in files])):
                    syms = sorted((n for n in nodes if not is_file_node(n)), key=lambda n: (line_of(n), n['label']))
                    leaves = [{'name': lname, 'kind': leaf_kind(n), 'loc': f'{src}:{line_of(n)}'}
                              for n, lname in zip(syms, unique([n['label'] for n in syms]))]
                    services.append({'name': name, 'loc': f'{src}:1', 'leaves': leaves})
                    order.append(((repo, src), [(repo, n['id']) for n in syms]))
                domains.append({'name': dom, 'services': services})
            repos.append({'name': repo, 'domains': domains})
        return {'meta': self.meta(title), 'repos': repos, 'edges': self.edge_list(order)}

    def edge_list(self, order):
        ids, file_ids, n = {}, {}, len(order)
        for i, (fkey, _) in enumerate(order): file_ids[fkey] = i
        for _, leaf_keys in order:
            for k in leaf_keys: ids[k] = n; n += 1
        # A file node is the service itself; any other node is its leaf.
        idx = lambda k: ids[k] if k in ids else file_ids[self.node_file[k]]
        best = {}
        for a, b, st in self.edges:
            pair = (idx(a), idx(b))
            if pair[0] != pair[1] and (pair not in best or CERTAINTY[st] < CERTAINTY[best[pair]]):
                best[pair] = st
        return [[a, b, st] for (a, b), st in sorted(best.items())]

    def meta(self, title):
        versions = sorted(v for v in self.versions if v)
        return {
            'label': 'Graphify',
            'title': title,
            'source': 'Graphify ' + ', '.join(versions) if versions else 'Graphify',
            'status': ['Extracted', 'Ambiguous', 'Unmatched', 'Inferred'],
            'kind': ['File', 'Function', 'Class', 'Other'],
        }
