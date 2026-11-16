"""Adapter out: HTTP links added to a Graphify graph as endpoint nodes with `calls_endpoint` and `serves` edges.

The shape follows Graphify's own HTTP endpoint extraction: a caller `calls_endpoint` an `http_endpoint` node, and the
endpoint `serves` the handler that answers it, all with context `http`. Pass the output of `graphify merge-graphs`,
whose node ids are 'repo::id' and whose nodes carry `repo`, and `graphify query/path/explain` then follow requests
from one repository into another; `graphify affected` follows them with `--relation calls_endpoint --relation serves`.
"""

import re
import unicodedata

from ...core.model import Status
from ..base import Presenter
from .node import GraphifyNode


class GraphifyId:
    """Node ids in Graphify's form: 'repo::' (merge-graphs' prefix) and then `make_id`'s lowercase word characters."""

    SEP = '::'
    NON_WORD = re.compile(r'[^\w]+')
    UNDERSCORES = re.compile(r'_+')
    EXTENSION = re.compile(r'\.[^./]*$')

    @classmethod
    def make(cls, repo: str, *parts: str) -> str:
        text = '_'.join(p.strip('_.') for p in parts if p)
        for _ in range(6):  # casefold and NFKC to a fixpoint, as Graphify's normalize_id does
            folded = unicodedata.normalize('NFKC', text.casefold())
            if folded == text:
                break
            text = folded
        local = cls.UNDERSCORES.sub('_', cls.NON_WORD.sub('_', text)).strip('_')
        return f'{repo}{cls.SEP}{local}'

    @classmethod
    def stem(cls, path: str) -> str:
        """'src/api.js' -> 'src/api': Graphify's file stem keeps every directory and drops the extension."""
        return cls.EXTENSION.sub('', path)


class GraphifyLinkWriter(Presenter):
    """A copy of a Graphify graph (or an empty one) with every linked endpoint as a node and every link as an edge.
    Unmatched calls have no endpoint to point at and are left out. The input graph is never modified, and what an
    earlier run of this writer added to it (marked `atlas` in its metadata) is dropped first, so writing twice adds
    nothing twice.

    A call starts at the input graph's node it sits in. A graph of one repository (`graphify update`) has no `repo` on
    its nodes, so its nodes are found by file alone; a call in a file the graph does not know gets a node of its own
    function, with the id Graphify would give it. Endpoint and client ids keep a ':' or '-', which Graphify's ids never
    have, so they cannot land on a node of the code.

    An endpoint `serves` its handler only when a merged graph has exactly one node of that name in the route's
    repository (a graph of one repository cannot tell which repository a name is in), and only for a handler read from
    the code: a broker channel found by its name has none. When several links join the same caller and endpoint, the
    edge keeps the most certain."""

    CONFIDENCE = {  # Graphify's rubric: EXTRACTED is 1.0; INFERRED takes a fixed rung; AMBIGUOUS stays at 0.1-0.3
        Status.MATCHED: ('EXTRACTED', 1.0),
        Status.INFERRED: ('INFERRED', 0.75),
        Status.AMBIGUOUS: ('AMBIGUOUS', 0.3),
    }
    CALLS = 'calls_endpoint'
    SERVES = 'serves'
    MARK = 'atlas'
    ENDPOINT = '::http:'  # in the ids of the nodes this writer adds, now and in its earlier calls_http output
    CLIENT = '::http-client'
    NO_HANDLER = 'named'  # Route.framework of a channel found by its name: its handler is the channel's name
    READ = 'read'  # Route.framework of a route a language model read, which the code then checked
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
        self._edges = {}  # (source, target, relation) -> (certainty, edge)
        self._by_file = {}  # only the input graph's nodes: a node added here encloses no other call
        self._by_name = {}
        for n in self._out['nodes']:
            self._index(GraphifyNode(n))
        for link in result:
            if link.route is not None:
                endpoint = self._endpoint(link.route)
                self._calls(self._source(link), endpoint, link)
                self._serve(endpoint, link.route)
        return self._out

    def _copy(self, data):
        out = {k: (list(v) if isinstance(v, list) else v) for k, v in self.EMPTY.items()}
        if data:
            out.update({k: v for k, v in data.items() if k not in ('nodes', 'links', 'edges')})
            out['nodes'] = [n for n in data.get('nodes', []) if not self._marked(n)]
            out['links'] = [e for e in data.get('links') or data.get('edges') or [] if not self._marked(e)]
        return out

    def _marked(self, item):
        """Added by this writer: marked, or (from before the mark) a calls_http edge or a node with this writer's id."""
        if self.MARK in (item.get('metadata') or {}) or item.get('relation') == 'calls_http':
            return True
        nid = str(item.get('id', ''))
        return self.ENDPOINT in nid or nid.endswith(self.CLIENT)

    def _index(self, node):
        if node.source_file:
            self._by_file.setdefault((node.repo, node.source_file), []).append(node)
        if not node.is_file:
            self._by_name.setdefault((node.repo, self._name(node.label)), []).append(node)

    def _add(self, node):
        if node['id'] not in self._ids:
            self._ids.add(node['id'])
            node.setdefault('metadata', {})[self.MARK] = {'added': True}
            self._out['nodes'].append(node)
        return node['id']

    def _endpoint(self, route):
        methods = sorted(route.methods)
        return self._add(
            {
                'id': f'{route.repo}{self.ENDPOINT}{"|".join(methods)} {route.path}',
                'label': f'{"|".join(methods)} {route.path}',
                'repo': route.repo,
                'file_type': 'code',
                'type': f'{route.protocol}_endpoint',
                'language': route.protocol,
                'source_file': route.file,
                'source_location': f'L{route.line}',
                'metadata': {
                    f'{route.protocol}_endpoint': {
                        'methods': methods,
                        'origin': 'backend',
                        'framework': route.framework,
                    }
                },
            }
        )

    def _source(self, link):
        call = link.call
        if call.is_payload:  # the URL is fetched by the target service, from code we cannot see statically
            return self._add(
                {
                    'id': f'{link.source}{self.CLIENT}',
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
                'id': GraphifyId.make(call.repo, GraphifyId.stem(call.file), call.function),
                'label': f'{call.function}()' if call.function else call.file,
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

    def _serve(self, endpoint, route):
        """endpoint -serves-> the handler's node, when the name picks out one node in the route's repository."""
        if not route.handler or route.framework == self.NO_HANDLER:
            return
        found = self._by_name.get((route.repo, self._name(route.handler.rsplit('.', 1)[-1])), [])
        if len(found) == 1:
            status = Status.INFERRED if route.framework == self.READ else Status.MATCHED
            key = (endpoint, found[0].id, self.SERVES)
            self._link(
                key, route.protocol, route, self.CONFIDENCE[status], {'handler': route.handler}, status.certainty
            )

    @staticmethod
    def _name(label):
        """'placeOrder()' and '.placeOrder()' -> 'placeOrder'."""
        return label.removesuffix('()').lstrip('.')

    def _calls(self, source, endpoint, link):
        confidence, score = self.CONFIDENCE[link.status]
        mark = {'status': link.status.name.lower(), 'reason': link.reason, 'verified': link.verification.value}
        key = (source, endpoint, self.CALLS)
        self._link(key, link.route.protocol, link.call, (confidence, score), mark, link.status.certainty)

    def _link(self, key, context, site, confidence, mark, certainty):
        """One edge (key: source, target, relation); of several with the same key, the most certain (lower) one wins.
        site: the call or route it was read at."""
        old = self._edges.get(key)
        if old is not None and old[0] <= certainty:
            return
        if old is not None:
            self._out['links'].remove(old[1])
        source, target, relation = key
        edge = {
            'source': source,
            'target': target,
            'relation': relation,
            'context': context,
            'confidence': confidence[0],
            'confidence_score': confidence[1],
            'source_file': site.file,
            'source_location': f'L{site.line}',
            'weight': 1.0,
            'metadata': {self.MARK: mark},
        }
        self._edges[key] = (certainty, edge)
        self._out['links'].append(edge)
