"""TrpcRoutes: the procedures a tRPC server serves over HTTP, each a route '<prefix>/<dotted path>'."""

from typing import NamedTuple

from .....core.http import Extraction
from ...kit import RouteCollector
from ..syntax.nodes import JsSyntax
from ..values.urls import UrlText
from .names import TrpcNames
from .routers import RouterTree


class Adapter(NamedTuple):
    """A function of a tRPC adapter that serves a router given as its options' `router`, and where the path its
    procedures are served under is written: an option (`basePath`, `endpoint`), or MOUNT, the prefix of the
    `app.use('/trpc', middleware)` the middleware is handed to."""

    library: str
    name: str
    prefix: str
    required: bool = False  # the adapter has no default prefix: without one, where it serves is not known


class TrpcRoutes(RouteCollector):
    """The root router an adapter serves is read with RouterTree; each procedure is a route '<prefix>/<path>' (GET
    for a query, POST for a mutation, as tRPC's HTTP adapters take them), placed at its key in the router. A prefix
    that is not a known string, or a router that is not a tRPC router call, gives no routes."""

    framework = 'trpc'
    MOUNT = 'mount'
    ADAPTERS = (
        Adapter('@trpc/server/adapters/standalone', 'createHTTPServer', 'basePath'),
        Adapter('@trpc/server/adapters/standalone', 'createHTTPHandler', 'basePath'),
        Adapter('@trpc/server/adapters/fetch', 'fetchRequestHandler', 'endpoint', required=True),
        Adapter('@trpc/server/adapters/express', 'createExpressMiddleware', MOUNT, required=True),
    )
    MENTIONS = (b'@trpc/server/adapters/',)
    ROUTER = 'router'
    USE = 'use'

    def collect(self) -> Extraction:
        out = Extraction()
        linker, tree = self.workspace.linker(), RouterTree()
        for source in self.workspace.sources:
            if source.test or not source.mentions(*self.MENTIONS):
                continue
            module = self.workspace.module(source, linker)
            for call in JsSyntax.walk(source.root, {'call_expression'}):
                adapter = self._adapter(module, call)
                if adapter is not None:
                    out.routes += self._routes(module, call, adapter, tree)
            module.release()
        linker.release()
        return out

    def _adapter(self, module, call):
        fn = call.child_by_field_name('function')
        return next((a for a in self.ADAPTERS if TrpcNames.imported(module, fn, a.library, {a.name})), None)

    def _routes(self, module, call, adapter, tree):
        args = JsSyntax.args(call)
        options = module.objects.locate(args[0]) if args else None
        if options is None or JsSyntax.unwrap(options.node).type != 'object':
            return []
        prefix = self._prefix(module, call, options, adapter)
        given = JsSyntax.prop(options.node, self.ROUTER)
        router = options.module.objects.origin(given) if given is not None else None
        if prefix is None or not TrpcNames.is_router(router):
            return []
        return [
            self.route(p.source, p.line, f'{prefix}/{p.path}', {p.method}, p.handler) for p in tree.procedures(router)
        ]

    def _prefix(self, module, call, options, adapter):
        """The path the procedures are served under ('' for the root), or None when it is not known."""
        if adapter.prefix == self.MOUNT:
            node = self._mount(call)
        else:
            node = JsSyntax.prop(options.node, adapter.prefix)
            module = options.module
        if node is None:
            return None if adapter.required else ''
        value = module.values.resolve(node, set())
        if value is None or not value.startswith('/') or UrlText.PLACEHOLDER.search(value):
            return None
        return value.rstrip('/')

    def _mount(self, call):
        """The prefix argument of `x.use('/prefix', <call>)` when the call is handed to one, else None."""
        args = JsSyntax.outer_parent(call)
        use = args.parent if args is not None and args.type == 'arguments' else None
        fn = JsSyntax.unwrap(use.child_by_field_name('function')) if use is not None else None
        if (
            fn is None
            or fn.type != 'member_expression'
            or JsSyntax.text(fn.child_by_field_name('property')) != self.USE
        ):
            return None
        given = JsSyntax.args(use)
        return given[0] if len(given) > 1 and JsSyntax.unwrap(given[0]).type == 'string' else None
