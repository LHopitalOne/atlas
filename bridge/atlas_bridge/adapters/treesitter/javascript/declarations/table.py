"""RouteSyntaxes: which syntax reads a member call, by the name of the method called."""

from ..syntax.site import CallSite
from .mounts import MountSyntax, RegisterSyntax
from .records import Declaration
from .routes import FastifyRouteSyntax, VerbRoutes


class RouteSyntaxes:
    """The declaration syntaxes of one file: `x.use(...)` and `x.register(...)` mount, `x.route({...})` is Fastify's,
    a verb call is a chained or direct route. Plain calls (`get(...)`) declare nothing."""

    def __init__(self, receivers):
        verbs = VerbRoutes(receivers)
        self._by_name = {'use': MountSyntax(), 'register': RegisterSyntax(), 'route': FastifyRouteSyntax()}
        self._by_name.update((verb, verbs) for verb in CallSite.ROUTE_VERBS)

    def declaration(self, site: CallSite) -> Declaration | None:
        """What the call declares about routes, or None."""
        syntax = self._by_name.get(site.name) if site.is_member else None
        return syntax.declaration(site) if syntax is not None else None
