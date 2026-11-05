"""The ways a route is declared: `app.get('/p', h)`, `router.route('/p').get(h)`, `fastify.route({method, url})`."""

from .....core.http import ANY
from ..syntax.nodes import JsSyntax
from ..syntax.site import CallSite
from .records import RouteDeclaration
from .syntax import DeclarationSyntax


class RouteSyntax(DeclarationSyntax):
    """One way of declaring a route."""

    HANDLERS = frozenset({'identifier', 'member_expression'})  # handlers with a name worth keeping

    @staticmethod
    def methods(verb):
        """The methods of a route verb: 'get' -> {GET}, 'del' -> {DELETE}, 'all' or none -> {ANY}."""
        v = (verb or '').lower()
        if v == 'all' or not v:
            return frozenset({ANY})
        return frozenset({CallSite.method_of(v)})

    def _declare(self, receiver, path, methods, handlers, node):
        handler = ''
        if handlers:
            last = JsSyntax.unwrap(handlers[-1])
            if last.type in self.HANDLERS:
                handler = JsSyntax.text(last)
        return RouteDeclaration(JsSyntax.text(receiver), path, methods, handler, JsSyntax.line(node))


class ChainedRouteSyntax(RouteSyntax):
    """`router.route('/book').get(getBook).put(putBook)`: each verb of the chain is a route of the path."""

    def declaration(self, site):
        n = site.receiver
        while n.type == 'call_expression':
            f = n.child_by_field_name('function')
            if f.type != 'member_expression':
                break
            prop = JsSyntax.text(f.child_by_field_name('property'))
            inner = JsSyntax.args(n)
            if prop == 'route' and inner and self.is_string(inner[0]):
                receiver = JsSyntax.unwrap(f.child_by_field_name('object'))
                path = JsSyntax.string(JsSyntax.unwrap(inner[0]))
                return self._declare(receiver, path, self.methods(site.name), site.args, site.node)
            if prop not in CallSite.ROUTE_VERBS:
                break
            n = JsSyntax.unwrap(f.child_by_field_name('object'))
        return None


class VerbRouteSyntax(RouteSyntax):
    """`app.get('/orders/:id', auth, getOrder)` on a router; koa-router's `router.get('name', '/path', h)` too."""

    def __init__(self, receivers):
        self._receivers = receivers

    def declaration(self, site):
        args = site.args
        strings = [i for i, a in enumerate(args[:2]) if self.is_string(a)]
        if not strings or len(args) < 2 or not self._receivers.is_router(site.receiver):
            return None
        i = strings[-1] if len(strings) == 2 else strings[0]
        if i == len(args) - 1:
            return None  # a path and no handler
        path = JsSyntax.string(JsSyntax.unwrap(args[i]))
        return self._declare(site.receiver, path, self.methods(site.name), args[i + 1 :], site.node)


class VerbRoutes(RouteSyntax):
    """The route a verb call declares, chained or direct (asked in that order); None for a request such as
    `api.get(url)`."""

    def __init__(self, receivers):
        self._syntaxes = (ChainedRouteSyntax(), VerbRouteSyntax(receivers))

    def declaration(self, site):
        for syntax in self._syntaxes:
            found = syntax.declaration(site)
            if found is not None:
                return found
        return None


class FastifyRouteSyntax(RouteSyntax):
    """`fastify.route({method: ['GET', 'POST'], url: '/f/:id', handler})`."""

    def declaration(self, site):
        if not site.args or JsSyntax.unwrap(site.args[0]).type != 'object':
            return None
        config = site.args[0]
        url = JsSyntax.prop(config, 'url') or JsSyntax.prop(config, 'path')
        if url is None or not self.is_string(url):
            return None
        handler = JsSyntax.prop(config, 'handler')
        path = JsSyntax.string(JsSyntax.unwrap(url))
        return self._declare(site.receiver, path, self._methods_of(config), [handler] if handler else [], site.node)

    def _methods_of(self, config):
        method = JsSyntax.prop(config, 'method')
        if method is None:
            return frozenset({ANY})
        method = JsSyntax.unwrap(method)
        values = [method] if method.type == 'string' else [x for x in method.named_children if x.type == 'string']
        if not values:
            return frozenset({ANY})
        return frozenset().union(*(self.methods(JsSyntax.string(v)) for v in values))
