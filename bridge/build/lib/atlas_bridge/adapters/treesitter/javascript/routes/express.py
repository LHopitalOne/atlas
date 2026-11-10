"""ExpressRoutes: the routes of Express, Koa-router, Fastify and Hono apps, with the prefixes they are mounted under."""

from .....core.http import Extraction
from ...kit import RouteCollector
from ..collector import FileCollector
from .files import FileRoutes
from .mounts import MountGraph
from .paths import ExpressPath


class ExpressRoutes(RouteCollector, FileCollector):
    """`app.get('/orders/:id', h)`, `router.route('/p').get(h).post(h)`, `fastify.route({method, url, handler})`.
    `app.use('/prefix', router)` prefixes the routes of `router` when it is defined in the same file or imported from
    another file of the repository. Only the files that declare a route or a mount are kept until the pass ends."""

    framework = 'express'

    def start(self):
        self._files = {}  # file path -> FileRoutes, for files that declare something

    def read(self, module):
        found = FileRoutes(module)
        for site in module.sites():
            try:
                declaration = module.route_syntax.declaration(site)
            except RecursionError:  # pragma: no cover - pathological nesting
                continue
            if declaration is not None:
                declaration.add_to(found)
        if found:
            self._files[module.path] = found

    def keeps(self, module):
        found = self._files.get(module.path)
        return found is not None and found.module is module

    def finish(self) -> Extraction:
        files, self._files = list(self._files.values()), {}
        mounts = MountGraph(files)
        out = Extraction()
        for f in files:
            for decl in f.routes:
                for prefix in mounts.prefixes(f, decl):
                    path = ExpressPath.canonical(ExpressPath.join(prefix, decl.path))
                    out.routes.append(self.route(f.module.source, decl.line, path, decl.methods, decl.handler))
        return out
