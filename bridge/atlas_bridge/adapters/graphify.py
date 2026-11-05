"""Adapter in: Graphify's graph.json (NetworkX node-link data, already parsed) into the code graph model.

  file node   a node whose label is its source file's name; it stands for the file itself
  symbols     every other node with a source file: functions, classes, constants, doc sections
  community   the Graphify community most of a file's nodes belong to
  links       every relation except the structural ones (a file contains its symbols, a class its methods);
              EXTRACTED -> matched, AMBIGUOUS -> ambiguous, INFERRED -> inferred
Nodes without a source file (external modules) and comment ("rationale") nodes are left out.
"""

import posixpath
import re
from collections import Counter

from ..core.model import CodeGraph, Community, Kind, Ref, Status, Symbol

STRUCTURAL = {'contains', 'method', 'rationale_for'}
STATUS = {'EXTRACTED': Status.MATCHED, 'AMBIGUOUS': Status.AMBIGUOUS, 'INFERRED': Status.INFERRED}
SKIP_TYPES = {'rationale'}


def line_of(node):
    m = re.match(r'L(\d+)', node.get('source_location') or '')
    return int(m.group(1)) if m else 0


def is_file_node(node):
    return not node.get('_callable') and node.get('label') == posixpath.basename(node['source_file'])


def kind_of(node):
    if node.get('_callable_class'):
        return Kind.CLASS
    return Kind.FUNCTION if node.get('_callable') else Kind.OTHER


def majority_community(nodes):
    votes = Counter((n['community'], n.get('community_name') or '') for n in nodes if 'community' in n)
    if not votes:
        return None
    (cid, name), _ = min(votes.items(), key=lambda kv: (-kv[1], kv[0][0]))
    return Community(cid, name)


def read(graph: CodeGraph, data: dict, repo: str):
    """Add one graph.json to `graph`. `repo` names it unless its nodes carry a `repo` (merge-graphs output)."""
    version = (data.get('graph') or {}).get('graphify_version')
    graph.tools.add(f'Graphify {version}' if version else 'Graphify')
    refs, by_file = {}, {}
    for n in data['nodes']:
        if not n.get('source_file') or n.get('file_type') in SKIP_TYPES:
            continue
        f = graph.file(n.get('repo') or repo, n['source_file'])
        by_file.setdefault(f.ref, (f, []))[1].append(n)
        if is_file_node(n):
            refs[n['id']] = f.ref
        else:
            f.symbols.append(Symbol(n['id'], n['label'], kind_of(n), line_of(n)))
            refs[n['id']] = Ref(f.repo, f.path, n['id'])
    for f, nodes in by_file.values():
        f.community = majority_community(nodes)
        f.symbols.sort(key=lambda s: (s.line, s.name))
    for e in data.get('links') or data.get('edges') or []:
        a, b = refs.get(e['source']), refs.get(e['target'])
        if a and b and e.get('relation') not in STRUCTURAL:
            graph.link(a, b, STATUS.get(e.get('confidence'), Status.INFERRED))
