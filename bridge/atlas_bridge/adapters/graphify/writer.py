"""Adapter out: HTTP links added to a Graphify graph as endpoint nodes and `calls_http` edges.

Pass the output of `graphify merge-graphs`, whose node ids are 'repo::id' and whose nodes carry `repo`, and
`graphify query/path/explain` then follow requests from one repository into another.
"""

from ...core.model import Status
from ..base import Presenter
from .node import GraphifyNode


class GraphifyLinkWriter(Presenter):
    """A copy of a Graphify graph (or an empty one) with every linked endpoint as a node and every link as an edge.
    Unmatched calls have no endpoint to point at and are left out. The input graph is never modified.

    A call starts at the input graph's node it sits in. A graph of one repository (`graphify update`) has no `repo` on
    its nodes, so its nodes are found by file alone; a call in a file the graph does not know gets a node of its own
    function."""

    CONFIDENCE = {
        Status.MATCHED: ('EXTRACTED', 1.0),
        Status.INFERRED: ('INFERRED', 0.6),
        Status.AMBIGUOUS: ('AMBIGUOUS', 0.3),
    }
    EMPTY = {'directed': True, 'multigraph': False, 'graph': {}, 'nodes': [], 'links': [], 'hyperedges': []}

    def __init__(self, base: dict | None = None):
        self._base = base

    @staticmethod
    def add_checked(graph: dict, pairs) -> dict:
        """Mark the edges a SCIP index shows (pairs of node ids): an edge the graph has becomes extracted and `scip`,
        a missing one is added as a `uses` edge. `graphify query/path` then walk what the compiler-grade index saw."""
        edges = {(e.get('source'), e.get('target')): e for e in graph['links']}
        for a, b in pairs:
            e = edges.get((a, b))
            if e is None:
                e = {'source': a, 'target': b, 'relation': 'uses'}
                graph['links'].append(e)
                edges[(a, b)] = e
            e.update({'confidence': 'EXTRACTED', 'confidence_score': 1.0, 'scip': True})
        return graph

    def present(self, result):
        """result: the links (usecases.link.Link) to add."""
        self._out = self._copy(self._base)
        self._ids = {n['id'] for n in self._out['nodes']}
        self._by_file = {}  # only the input graph's nodes: a node added here encloses no other call
        for n in self._out['nodes']:
            self._index(n)
        for link in result:
            if link.route is not None:
                self._out['links'].append(self._edge(link, self._source(link), self._endpoint(link.route)))
        return self._out

    def _copy(self, data):
        out = {k: (list(v) if isinstance(v, list) else v) for k, v in self.EMPTY.items()}
        if data:
            out.update({k: v for k, v in data.items() if k not in ('nodes', 'links', 'edges')})
            out['nodes'] = list(data.get('nodes', []))
            out['links'] = list(data.get('links') or data.get('edges') or [])
        return out

    def _index(self, node):
        if node.get('source_file'):
            self._by_file.setdefault((node.get('repo') or '', node['source_file']), []).append(GraphifyNode(node))

    def _add(self, node):
        if node['id'] not in self._ids:
            self._ids.add(node['id'])
            self._out['nodes'].append(node)
        return node['id']

    def _endpoint(self, route):
        methods = '|'.join(sorted(route.methods))
        return self._add(
            {
                'id': f'{route.repo}::http:{methods} {route.path}',
                'label': f'{methods} {route.path}',
                'repo': route.repo,
                'file_type': 'code',
                'source_file': route.file,
                'source_location': f'L{route.line}',
                'type': 'http_endpoint',
            }
        )

    def _source(self, link):
        call = link.call
        if call.is_payload:  # the URL is fetched by the target service, from code we cannot see statically
            return self._add(
                {
                    'id': f'{link.source}::http-client',
                    'label': f'{link.source} HTTP client',
                    'repo': link.source,
                    'file_type': 'code',
                    'source_file': '(fetches URLs it is given)',
                    'type': 'http_client',
                }
            )
        enclosing = self._enclosing(call)
        if enclosing:
            return enclosing.id
        return self._add(
            {
                'id': f'{call.repo}::{call.file}::{call.function or "module"}',
                'label': call.function or call.file,
                'repo': call.repo,
                'file_type': 'code',
                'source_file': call.file,
                'source_location': f'L{call.line}',
                '_callable': True,
            }
        )

    def _enclosing(self, call):
        """The node a call sits in: its function's node by name (line numbers in a graph built from an older checkout
        drift), the file node for a call outside any named function, else the last symbol starting at or before its
        line."""
        nodes = self._by_file.get((call.repo, call.file)) or self._by_file.get(('', call.file), [])
        named = [n for n in nodes if not n.is_file and self._name(n.label) == call.function]
        if named:
            return min(named, key=lambda n: abs(n.line - call.line))
        files = [n for n in nodes if n.is_file]
        if not call.function and files:
            return files[0]
        best = None
        for n in nodes:
            if n.line <= call.line and (best is None or n.line >= best.line):
                best = n
        return best

    @staticmethod
    def _name(label):
        """'placeOrder()' and '.placeOrder()' -> 'placeOrder'."""
        return label.removesuffix('()').lstrip('.')

    def _edge(self, link, source, target):
        confidence, weight = self.CONFIDENCE[link.status]
        return {
            'source': source,
            'target': target,
            'relation': 'calls_http',
            'confidence': confidence,
            'confidence_score': weight,
            'source_file': link.call.file,
            'source_location': f'L{link.call.line}',
            'weight': 1.0,
            'context': link.reason,
            'verified': link.verification.value,
        }
