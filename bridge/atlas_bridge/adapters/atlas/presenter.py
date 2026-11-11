"""Adapter out: present a MapView as an Atlas graph spec (docs/GRAPH_SPEC.md).

Atlas numbers nodes by position: every file (service) first, in map order, then every leaf, walking the files in
that same order: a file's symbols, then the HTTP endpoints it declares. Links become [source id, target id, status].
With an HttpLayer the spec also carries the proof of every HTTP link (`links`), the requests no route was found
for (`unmatched`), each repository's address and commit, and how accurate the links are (`meta.accuracy`).
"""

import posixpath
from collections import Counter

from ...core.model import Kind, Ref
from ...usecases.draw import MapView
from ..base import Presenter
from .http import HttpLayer, NodeIds


class AtlasSpecPresenter(Presenter):
    KIND_NAMES = ['File', 'Function', 'Class', 'Other']
    STATUS_NAMES = ['Extracted', 'Ambiguous', 'Unmatched', 'Inferred']
    # with HTTP links, endpoints take the diamond: functions and classes share the circle
    HTTP_KIND_NAMES = ['File', 'Function or class', 'HTTP endpoint', 'Symbol']
    HTTP_KIND = {Kind.FUNCTION: 1, Kind.CLASS: 1, Kind.OTHER: 3}

    def __init__(self, title='Graphify graph', http: HttpLayer | None = None, descriptions=None, doc_model=''):
        """descriptions: {(repo, path): core.descriptions.Description} written by `doc_model`, shown on the files'
        services as `doc` (the summary) and `tags` (the role, then the domain words)."""
        self._title = title
        self._http = http
        self._descriptions = descriptions or {}
        self._doc_model = doc_model

    def present(self, result: MapView):
        files = [f for r in result.repos for d in r.domains for f in d.files]
        ids = {f.ref: i for i, f in enumerate(files)}
        for f in files:
            for s in f.symbols:
                ids[Ref(f.repo, f.path, s.id)] = len(ids)
            for e in self._endpoints(f.ref):
                ids[e.ref] = len(ids)
        spec = {
            'meta': self._meta(result),
            'repos': [self._repo(r) for r in result.repos],
            'edges': sorted(
                self._edge(ids, a, b, st, result.graph.checked) for (a, b), st in result.graph.links.items()
            ),
        }
        if self._http is not None:
            self._add_links(spec, result, NodeIds(ids, {f.ref: f.symbols for f in files}))
        return spec

    @staticmethod
    def _edge(ids, a, b, status, checked):
        """[source, target, status], with a fourth item, 1, when a SCIP index shows the edge."""
        return [ids[a], ids[b], int(status), 1] if (a, b) in checked else [ids[a], ids[b], int(status)]

    def _meta(self, result):
        meta = {
            'label': 'Graphify',
            'title': self._title,
            'source': ', '.join(sorted(result.graph.tools)),
            'status': self.STATUS_NAMES,
            'kind': self.HTTP_KIND_NAMES if self._http else self.KIND_NAMES,
        }
        if self._http is not None and self._http.accuracy:
            meta['accuracy'] = self._http.accuracy
        if self._descriptions:
            meta['docSource'] = 'ai'
            meta['docModel'] = self._doc_model
        return meta

    def _repo(self, r):
        out = {'name': r.name}
        if self._http is not None:
            out.update(self._http.origin(r.name))
        out['domains'] = [{'name': d.name, 'services': self._services(d.files)} for d in r.domains]
        return out

    def _add_links(self, spec, result, nodes):
        edges, links, unmatched = self._http.present(nodes, [r.name for r in result.repos])
        merged = {(e[0], e[1]): e[2:] for e in spec['edges']}
        merged.update({k: [st] for k, st in edges.items()})  # an HTTP link is better evidence than an import or a name
        spec['edges'] = sorted([a, b, *rest] for (a, b), rest in merged.items())
        spec['links'] = links
        spec['unmatched'] = unmatched

    def _endpoints(self, ref):
        return self._http.endpoints(ref) if self._http is not None else []

    def _kind(self, kind):
        return self.HTTP_KIND[kind] if self._http is not None else int(kind)

    def _services(self, files):
        out = []
        for f, name in zip(files, self.unique(posixpath.basename(f.path) for f in files), strict=True):
            leaves = [
                {'name': leaf_name, 'kind': self._kind(s.kind), 'loc': f'{f.path}:{s.line}'}
                for s, leaf_name in zip(f.symbols, self.unique(s.name for s in f.symbols), strict=True)
            ]
            leaves += [e.leaf() for e in self._endpoints(f.ref)]
            service = {'name': name, 'loc': f'{f.path}:1', 'leaves': leaves}
            described = self._descriptions.get((f.repo, f.path))
            if described is not None:
                service.update(doc=described.summary, tags=[described.role, *described.tags])
            out.append(service)
        return out

    @staticmethod
    def unique(names):
        """Repeated names get ' (2)', ' (3)' so every name in a group is distinct."""
        seen, out = Counter(), []
        for n in names:
            seen[n] += 1
            out.append(n if seen[n] == 1 else f'{n} ({seen[n]})')
        return out
