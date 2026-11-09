"""HTTP links on the Atlas map: every route a link reaches becomes an endpoint leaf on the file that declares it,
every link an edge from the function that sends the request to that endpoint, and every link keeps its proof
(both lines of code, the method and path, and how sure we are) in the spec's `links` list."""

from dataclasses import dataclass

from ...core.model import CodeGraph, Ref, Status
from .records import LinkRecord, RouteSite
from .source import CodeSource


@dataclass(frozen=True)
class Endpoint:
    """A route as a leaf on the map. Several links can reach the same one."""

    route: RouteSite

    KIND = 2  # drawn as a diamond; see AtlasSpecPresenter.HTTP_KIND_NAMES

    @property
    def ref(self):
        r = self.route
        return Ref(r.repo, r.file, f'http:{r.label}@{r.line}')

    def leaf(self):
        r = self.route
        served = f'{r.handler} ({r.framework})' if r.handler and r.framework else r.handler or r.framework
        return {
            'name': r.label,
            'kind': self.KIND,
            'loc': f'{r.file}:{r.line}',
            'doc': f'HTTP route served by {served}.' if served else 'HTTP route.',
            'sig': f'{r.label} -> {r.handler}' if r.handler else r.label,
        }


class HttpLayer:
    """Adds HTTP links to a map. Call add_files() on the code graph before drawing it, so every file a link
    touches is on the map, then let AtlasSpecPresenter ask for endpoints() and present() while it numbers nodes."""

    def __init__(self, records: list[LinkRecord], source: CodeSource | None = None, accuracy: dict | None = None):
        self._records = records
        self._source = source or CodeSource()
        self.accuracy = accuracy
        self._endpoints: dict[Ref, list[Endpoint]] = {}
        for r in records:
            if r.route is not None:
                e = Endpoint(r.route)
                at = self._endpoints.setdefault(Ref(r.route.repo, r.route.file), [])
                if e not in at:
                    at.append(e)

    def add_files(self, graph: CodeGraph):
        for r in self._records:
            graph.file(r.call.repo, r.call.file)
            if r.route is not None:
                graph.file(r.route.repo, r.route.file)

    def endpoints(self, file: Ref) -> list[Endpoint]:
        return sorted(self._endpoints.get(file, []), key=lambda e: (e.route.line, e.route.label))

    def origin(self, repo: str) -> dict:
        o = self._source.origin(repo)
        return {k: v for k, v in (('url', o.url), ('commit', o.commit)) if v}

    def present(self, nodes: 'NodeIds', repos: list[str]):
        """(edges as {(source, target): status}, links, unmatched) with node ids from `nodes`."""
        index = {name: i for i, name in enumerate(repos)}
        edges, links, unmatched = {}, [], []
        for r in self._records:
            source = nodes.enclosing(r.call)
            if r.route is None:
                unmatched.append(self._unmatched(r, source, index))
                continue
            target = nodes.ids[Endpoint(r.route).ref]
            old = edges.get((source, target))
            if old is None or Status(r.edge_status).certainty < Status(old).certainty:
                edges[(source, target)] = r.edge_status
            links.append(self._link(r, source, target, index))
        return edges, links, unmatched

    def _link(self, r, source, target, index):
        route = r.route
        return {
            'from': source,
            'to': target,
            'method': r.call.method or '|'.join(route.methods),
            'path': route.path,
            'proof': r.proof,
            'reason': r.reason,
            'call': self._site(index[r.call.repo], r.call.repo, r.call.file, r.call.line, function=r.call.function),
            'route': self._site(
                index[route.repo],
                route.repo,
                route.file,
                route.line,
                handler=route.handler,
                framework=route.framework,
                methods=list(route.methods),
            ),
            'checks': [{'at': c.at, 'name': c.name, 'means': c.means, 'verdict': c.verdict} for c in r.checks],
        }

    def _unmatched(self, r, source, index):
        return {
            'from': source,
            'method': r.call.method,
            'path': r.call.path,
            'target': index.get(r.target, -1),
            'reason': r.reason,
            'call': self._site(index[r.call.repo], r.call.repo, r.call.file, r.call.line, function=r.call.function),
        }

    def _site(self, repo_id, repo, file, line, **extra):
        start, code = self._source.snippet(repo, file, line)
        site = {'repo': repo_id, 'file': file, 'line': line, **{k: v for k, v in extra.items() if v}}
        if code:
            site.update(start=start, code=code)
        return site


class NodeIds:
    """Atlas node ids by Ref, plus the files on the map, to find the function a request is sent from."""

    def __init__(self, ids: dict[Ref, int], files: dict[Ref, list]):
        self.ids = ids
        self._files = files  # file ref -> its symbols (core.model.Symbol), sorted by line

    def enclosing(self, call) -> int:
        """The last symbol in the call's file that starts at or before its line, else the file itself."""
        file = Ref(call.repo, call.file)
        best = None
        for s in self._files.get(file, []):
            if 0 < s.line <= call.line:
                best = s
        return self.ids[Ref(call.repo, call.file, best.id)] if best else self.ids[file]
