"""Flask and FastAPI routes: `@app.route(...)`, `@router.get(...)` decorators and `app.add_url_rule(...)`."""

from .....core.http import ANY, Protocol
from ..syntax import PythonSyntax
from ..verbs import HttpVerbs
from .prefixed import PrefixedRoutes, RouteDeclaration


class DecoratorRoutes(PrefixedRoutes):
    """`@app.route('/p', methods=[...])`, `@bp.get('/p')`, `@router.api_route(...)`, `@app.websocket(...)` on a
    function: the function is the handler, the verb (GET for route) the method unless `methods=` says otherwise.
    `websocket` and `websocket_route` (FastAPI, Starlette) declare a WebSocket endpoint: any operation on its path."""

    WEBSOCKETS = frozenset({'websocket', 'websocket_route'})
    ROUTE_DECORATORS = frozenset({'route', 'api_route'}) | WEBSOCKETS

    def _declarations(self):
        for source, decorated in self.workspace.decorated():
            definition = decorated.child_by_field_name('definition')
            if definition is not None and definition.type == 'function_definition':
                handler = PythonSyntax.name(definition)
                for d in decorated.children:
                    declaration = self._decorator(source, d, handler)
                    if declaration is not None:
                        yield declaration

    def _decorator(self, source, decorator, handler):
        expr = decorator.named_children[0] if decorator.type == 'decorator' and decorator.named_children else None
        if expr is None or expr.type != 'call':
            return None
        fn = expr.child_by_field_name('function')
        if fn.type != 'attribute':
            return None
        attr = PythonSyntax.text(fn.child_by_field_name('attribute'))
        if attr not in self.ROUTE_DECORATORS and attr not in HttpVerbs.NAMES:
            return None
        pos, kw = PythonSyntax.call_args(expr)
        node = pos[0] if pos else kw.get('path', kw.get('rule'))
        verb = [attr.upper()] if attr in HttpVerbs.NAMES else ['GET']
        receiver = fn.child_by_field_name('object')
        if attr in self.WEBSOCKETS:
            return RouteDeclaration(source, decorator, receiver, node, None, [ANY], handler, Protocol.WEBSOCKET)
        return RouteDeclaration(source, decorator, receiver, node, kw.get('methods'), verb, handler)


class UrlRuleRoutes(PrefixedRoutes):
    """`app.add_url_rule('/p', 'endpoint', view_func=view, methods=[...])`: GET unless `methods=` says otherwise."""

    NAMES = frozenset({'add_url_rule'})

    def _declarations(self):
        for source, call, _ in self.workspace.calls(self.NAMES):
            yield self._rule(source, call)

    @staticmethod
    def _rule(source, call):
        pos, kw = PythonSyntax.call_args(call)
        node = pos[0] if pos else kw.get('rule')
        view = kw.get('view_func', pos[2] if len(pos) > 2 else None)
        handler = PythonSyntax.text(view) if view is not None else ''
        receiver = PythonSyntax.receiver(call)
        return RouteDeclaration(source, call, receiver, node, kw.get('methods'), ['GET'], handler)
