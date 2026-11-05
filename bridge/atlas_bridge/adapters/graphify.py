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


# ---------------------------------------------------------------- out: HTTP links as Graphify nodes and edges

CONFIDENCE = {
    Status.MATCHED: ('EXTRACTED', 1.0),
    Status.INFERRED: ('INFERRED', 0.6),
    Status.AMBIGUOUS: ('AMBIGUOUS', 0.3),
}


def _enclosing(nodes_by_file, repo, path, line):
    """The node a call sits in: the last symbol in that file starting at or before the line, else the file node."""
    best = None
    for n in nodes_by_file.get((repo, path), []):
        start = line_of(n)
        if start <= line and (best is None or start >= line_of(best)):
            best = n
    return best


def with_links(data, links):
    """A copy of a Graphify graph (or an empty one) with every linked endpoint as a node and every link as an edge.

    Pass the output of `graphify merge-graphs`, whose node ids are 'repo::id' and whose nodes carry `repo`, and
    `graphify query/path/explain` then follow requests from one repository into another. Unmatched calls have no
    endpoint to point at and are left out.
    """
    out = {'directed': True, 'multigraph': False, 'graph': {}, 'nodes': [], 'links': [], 'hyperedges': []}
    if data:
        out.update({k: v for k, v in data.items() if k not in ('nodes', 'links', 'edges')})
        out['nodes'] = list(data.get('nodes', []))
        out['links'] = list(data.get('links') or data.get('edges') or [])
    by_file = {}
    for n in out['nodes']:
        if n.get('source_file'):
            by_file.setdefault((n.get('repo', ''), n['source_file']), []).append(n)
    ids = {n['id'] for n in out['nodes']}

    def add(node):
        if node['id'] not in ids:
            ids.add(node['id'])
            out['nodes'].append(node)
            by_file.setdefault((node['repo'], node['source_file']), []).append(node)
        return node['id']

    for link in links:
        if link.route is None:
            continue
        c, r = link.call, link.route
        methods = '|'.join(sorted(r.methods))
        target = add(
            {
                'id': f'{r.repo}::http:{methods} {r.path}',
                'label': f'{methods} {r.path}',
                'repo': r.repo,
                'file_type': 'code',
                'source_file': r.file,
                'source_location': f'L{r.line}',
                'type': 'http_endpoint',
            }
        )
        if c.kind == 'payload':  # the URL is fetched by the target service, from code we cannot see statically
            source = add(
                {
                    'id': f'{link.source}::http-client',
                    'label': f'{link.source} HTTP client',
                    'repo': link.source,
                    'file_type': 'code',
                    'source_file': '(fetches URLs it is given)',
                    'type': 'http_client',
                }
            )
        else:
            enclosing = _enclosing(by_file, c.repo, c.file, c.line)
            source = (
                enclosing['id']
                if enclosing
                else add(
                    {
                        'id': f'{c.repo}::{c.file}::{c.function or "module"}',
                        'label': c.function or c.file,
                        'repo': c.repo,
                        'file_type': 'code',
                        'source_file': c.file,
                        'source_location': f'L{c.line}',
                        '_callable': True,
                    }
                )
            )
        confidence, weight = CONFIDENCE[link.status]
        out['links'].append(
            {
                'source': source,
                'target': target,
                'relation': 'calls_http',
                'confidence': confidence,
                'confidence_score': weight,
                'source_file': c.file,
                'source_location': f'L{c.line}',
                'weight': 1.0,
                'context': link.reason,
            }
        )
    return out
