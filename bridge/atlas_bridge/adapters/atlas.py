"""Adapter out: present a MapView as an Atlas graph spec (docs/GRAPH_SPEC.md).

Atlas numbers nodes by position: every file (service) first, in map order, then every symbol (leaf), walking the
files in that same order. Links become [source id, target id, status].
"""

import posixpath
from collections import Counter

from ..core.model import Ref
from ..usecases.draw import MapView

KIND_NAMES = ['File', 'Function', 'Class', 'Other']
STATUS_NAMES = ['Extracted', 'Ambiguous', 'Unmatched', 'Inferred']


def unique(names):
    """Repeated names get ' (2)', ' (3)' so every name in a group is distinct."""
    seen, out = Counter(), []
    for n in names:
        seen[n] += 1
        out.append(n if seen[n] == 1 else f'{n} ({seen[n]})')
    return out


def present(view: MapView, title='Graphify graph'):
    files = [f for r in view.repos for d in r.domains for f in d.files]
    ids = {f.ref: i for i, f in enumerate(files)}
    for f in files:
        for s in f.symbols:
            ids[Ref(f.repo, f.path, s.id)] = len(ids)
    return {
        'meta': {
            'label': 'Graphify',
            'title': title,
            'source': ', '.join(sorted(view.graph.tools)),
            'status': STATUS_NAMES,
            'kind': KIND_NAMES,
        },
        'repos': [
            {'name': r.name, 'domains': [{'name': d.name, 'services': services(d.files)} for d in r.domains]}
            for r in view.repos
        ],
        'edges': sorted([ids[a], ids[b], int(st)] for (a, b), st in view.graph.links.items()),
    }


def services(files):
    out = []
    for f, name in zip(files, unique(posixpath.basename(f.path) for f in files), strict=True):
        leaves = [
            {'name': leaf_name, 'kind': int(s.kind), 'loc': f'{f.path}:{s.line}'}
            for s, leaf_name in zip(f.symbols, unique(s.name for s in f.symbols), strict=True)
        ]
        out.append({'name': name, 'loc': f'{f.path}:1', 'leaves': leaves})
    return out
