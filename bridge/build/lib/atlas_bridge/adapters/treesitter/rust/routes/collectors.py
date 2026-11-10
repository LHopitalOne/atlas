"""The route collectors: routers built in code (axum, actix-web builders) and actix-web attribute routes."""

import dataclasses

from .....core.http import Extraction
from ...kit import RouteCollector
from ..syntax import RustSyntax


class RustRouteCollector(RouteCollector):
    """A route collector reading the crate's router graph, which every route collector shares."""

    def __init__(self, workspace, graph):
        super().__init__(workspace)
        self._graph = graph


class RouterRoutes(RustRouteCollector):
    """Routes of the routers nobody mounts: axum `Router` chains and actix-web `App`/`scope` builders. The
    framework is the file's: 'actix' when it uses actix_web, else 'axum'."""

    framework = 'axum'

    def collect(self) -> Extraction:
        return Extraction([self.route(r.file, r.line, r.path, r.methods, r.handler) for r in self._graph.roots()])

    def route(self, source, *args, **kwargs):
        route = super().route(source, *args, **kwargs)
        return route if source.framework == self.framework else dataclasses.replace(route, framework=source.framework)


class ActixAttributeRoutes(RustRouteCollector):
    """`#[get("/p")] async fn handler()` routes outside test code whose handler no builder mounts (those come with
    their scope, through the graph)."""

    framework = 'actix'

    def __init__(self, workspace, graph, attributes):
        super().__init__(workspace, graph)
        self._attributes = attributes

    def collect(self) -> Extraction:
        routes = []
        for fn_key, attrs in self._attributes.items():
            if self._graph.is_mounted(fn_key):
                continue
            routes += [self._route(r) for r in attrs if not self.workspace.is_test(r.file, r.fn)]
        return Extraction(routes)

    def _route(self, attribute):
        return self.route(
            attribute.file, attribute.line, attribute.path, attribute.methods, RustSyntax.name(attribute.fn)
        )
