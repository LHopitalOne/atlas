"""Adapter out: HTTP links added to a Graphify graph as endpoint nodes and `calls_http` edges.

Pass the output of `graphify merge-graphs`, whose node ids are 'repo::id' and whose nodes carry `repo`, and
`graphify query/path/explain` then follow requests from one repository into another.
"""

from ...core.model import Status
from ..base import Presenter
from .node import GraphifyNode


class GraphifyLinkWriter(Presenter):
    """A copy of a Graphify graph (or an empty one) with every linked endpoint as a node and every link as an edge.
    Unmatched calls have no endpoint to point at and are left out. The input graph is never modified."""

    CONFIDENCE = {
        Status.MATCHED: ('EXTRACTED', 1.0),
        Status.INFERRED: ('INFERRED', 0.6),
        Status.AMBIGUOUS: ('AMBIGUOUS', 0.3),
    }
    EMPTY = {'directed': True, 'multigraph': False, 'graph': {}, 'nodes': [], 'links': [], 'hyperedges': []}

    def __init__(self, base: dict | None = None):
        self._base = base

    def present(self, result):
        """result: the links (usecases.link.Link) to add."""
        self._out = self._copy(self._base)
        self._ids = {n['id'] for n in self._out['nodes']}
        self._by_file = {}
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
            self._by_file.setdefault((node.get('repo', ''), node['source_file']), []).append(GraphifyNode(node))

    def _add(self, node):
        if node['id'] not in self._ids:
            self._ids.add(node['id'])
            self._out['nodes'].append(node)
            self._index(node)
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
        """The node a call sits in: the last symbol in its file starting at or before its line, else the file node."""
        best = None
        for n in self._by_file.get((call.repo, call.file), []):
            if n.line <= call.line and (best is None or n.line >= best.line):
                best = n
        return best

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
        }
