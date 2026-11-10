"""RustExtractor: HTTP routes (axum, actix-web) and requests (reqwest/hyper clients, request-trait impls), and TCP and
UDP channels both ways (std, tokio and async-std sockets), and gRPC services served with tonic.

Routes come from evaluating router expressions (`.route` chains, `.nest`, `.merge`, let-bound routers and crate fns
returning routers) and from actix-web attribute routes. Requests come from types implementing a request trait whose
`fn path` yields a literal, and from `client.get(url)` / `.request(Method::X, url)` calls. Channels come from calls to
the library entry points of channels.EntryPoints, their address followed through fns, struct fields and environment
defaults.
"""

from ....core.http import Extraction
from ..kit import LanguageExtractor
from .calls import CallOrder, ClientCalls, TraitPathCalls
from .channels import ChannelCalls, ChannelRoutes, ChannelSites, Followups
from .policy import RustTestPolicy
from .routes import ActixAttributeRoutes, ActixAttributes, RouterGraph, RouterRoutes, TonicServices, UniqueRoutes
from .values import ChannelValues, CrateFunctions, CrateStructs, RustValues, ValueTypes
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
        functions, structs = CrateFunctions(workspace), CrateStructs(workspace)
        types = ValueTypes(workspace, functions, structs)
        channels, sites = ChannelValues(workspace, functions, structs, types), ChannelSites(types)
        followups = Followups(workspace)
        return [
            RouterRoutes(workspace, graph),
            ActixAttributeRoutes(workspace, graph, attributes),
            ChannelRoutes(workspace, channels, sites, followups),
            TonicServices(workspace),
            TraitPathCalls(workspace, values),
            ClientCalls(workspace, values),
            ChannelCalls(workspace, channels, sites, followups),
        ]

    def extract(self, repo, files, paths) -> Extraction:
        """The template's extraction, with each route kept once (see UniqueRoutes) and calls file by file."""
        out = super().extract(repo, files, paths)
        out.routes = UniqueRoutes.first(out.routes)
        out.calls = CallOrder(paths).sorted(out.calls)
        return out
