"""RustExtractor: HTTP routes (axum, actix-web) and requests (reqwest/hyper clients, request-trait impls).

Routes come from evaluating router expressions (`.route` chains, `.nest`, `.merge`, let-bound routers and crate fns
returning routers) and from actix-web attribute routes. Requests come from types implementing a request trait whose
`fn path` yields a literal, and from `client.get(url)` / `.request(Method::X, url)` calls.
"""

from ....core.http import Extraction
from ..kit import LanguageExtractor
from .calls import CallOrder, ClientCalls, TraitPathCalls
from .policy import RustTestPolicy
from .routes import ActixAttributeRoutes, ActixAttributes, RouterGraph, RouterRoutes, UniqueRoutes
from .values import RustValues
from .workspace import RustWorkspace


class RustExtractor(LanguageExtractor):
    GRAMMARS = frozenset({'rust'})
    POLICY = RustTestPolicy

    def workspace(self, repo, sources) -> RustWorkspace:
        return RustWorkspace(repo, sources)

    def collectors(self, workspace) -> list:
        attributes = ActixAttributes(workspace.files)
        graph = RouterGraph(workspace, attributes)  # shared: attribute routes are roots only when no router mounts them
        values = RustValues(workspace)
        return [
            RouterRoutes(workspace, graph),
            ActixAttributeRoutes(workspace, graph, attributes),
            TraitPathCalls(workspace, values),
            ClientCalls(workspace, values),
        ]

    def extract(self, repo, files, paths) -> Extraction:
        """The template's extraction, with each route kept once (see UniqueRoutes) and calls file by file."""
        out = super().extract(repo, files, paths)
        out.routes = UniqueRoutes.first(out.routes)
        out.calls = CallOrder(paths).sorted(out.calls)
        return out
