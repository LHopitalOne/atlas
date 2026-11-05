"""Routes declared on Flask apps and blueprints and FastAPI apps and routers, with their prefixes."""

import dataclasses
from abc import abstractmethod
from typing import NamedTuple

from .....core.http import ANY, Extraction
from ...kit import RouteCollector
from ..scope import Scope
from ..syntax import PythonSyntax
from ..values import Marker, PythonValueResolver
from ..verbs import HttpVerbs
from .converters import FlaskPath


class RouteDeclaration(NamedTuple):
    """One route as code declares it, before its path and methods are resolved."""

    source: object
    site: object  # the decorator or call that declares it
    receiver: object  # the app, blueprint or router expression, or None
    path: object  # the path expression, or None
    methods: object  # the `methods=` expression, or None
    default: list  # the methods without `methods=`
    handler: str


class PrefixedRoutes(RouteCollector):
    """Base of the collectors whose routes hang off an app, blueprint or router object.

    Subclasses yield RouteDeclarations; this class resolves each to a route. The receiver's constructor names the
    framework (Blueprint/Flask/Quart: flask, APIRouter/FastAPI: fastapi) and its own prefix; a registration adds or
    replaces it (FastAPI prefixes add up, a Flask registration replaces).
    """

    FASTAPI = frozenset({'APIRouter', 'FastAPI'})
    FLASK = frozenset({'Blueprint', 'Flask', 'Quart'})
    SEQUENCES = ('list', 'tuple', 'set')

    def __init__(self, workspace, registrations):
        super().__init__(workspace)
        self._values = PythonValueResolver(workspace)
        self._registrations = registrations  # Registrations, shared

    def collect(self) -> Extraction:
        routes = []
        for declaration in self._declarations():
            route = self._route_of(declaration)
            if route is not None:
                routes.append(route)
        return Extraction(routes=routes)

    @abstractmethod
    def _declarations(self):
        """Every RouteDeclaration of this kind in the workspace."""

    def route(self, source, line, path, methods=frozenset({ANY}), handler='', name='', framework=''):
        """The kit's route, for the framework this receiver belongs to."""
        return dataclasses.replace(super().route(source, line, path, methods, handler, name), framework=framework)

    def _route_of(self, d: RouteDeclaration):
        """The route a declaration makes, or None when its path does not resolve to one."""
        if d.path is None:
            return None
        v = self._values.resolve(d.path, Scope.at(d.source, d.site))[0]
        raw = v.text
        if not v.is_literal or not self._reads_as_path(raw):
            return None
        methods = self._methods(d.source, d.site, d.methods) if d.methods is not None else d.default
        prefix, framework = self._prefix(d.source, d.receiver)
        if not raw and not prefix:
            return None  # '' names a router's own prefix; without one it is more likely some other decorator
        line = PythonSyntax.line(d.site)
        return self.route(d.source, line, FlaskPath.template(prefix + raw), methods, d.handler, '', framework)

    @staticmethod
    def _reads_as_path(raw):
        """'' (the router's own prefix), '/...' or a converter; never whitespace or an unresolved marker."""
        if Marker.is_unresolved(raw) or any(c.isspace() for c in raw):
            return False
        return raw == '' or raw.startswith('/') or '<' in raw

    def _prefix(self, source, receiver):
        framework = 'fastapi' if source.mentions(b'fastapi') else 'flask'
        found = self.workspace.names.value(source, receiver) if receiver is not None else None
        if found is None or found.node.type != 'call':
            return '', framework
        constructor = found.node
        callee = PythonSyntax.callee(constructor)
        if callee in self.FASTAPI:
            framework = 'fastapi'
        elif callee in self.FLASK:
            framework = 'flask'
        _, kw = PythonSyntax.call_args(constructor)
        node = kw.get('url_prefix', kw.get('prefix'))
        own = self._values.resolve(node, Scope.module(found.source))[0].text if node is not None else ''
        registered = self._registrations.prefix_for(found.source, constructor)
        if framework == 'fastapi':
            return (registered or '') + own, framework
        return (own if registered is None else registered), framework

    def _methods(self, source, site, node):
        """methods=[...] (a literal list or a module-level name for one); ANY when any entry is unknown."""
        if node.type in ('identifier', 'attribute'):
            found = self.workspace.names.value(source, node)
            if found is not None:
                source, node = found.source, found.node
            site = node
        if node.type not in self.SEQUENCES:
            return [ANY]
        out = []
        for m in node.named_children:
            v = self._values.resolve(m, Scope.at(source, site))[0]
            if not v.is_literal or not HttpVerbs.method(v.text):
                return [ANY]
            out.append(v.text.upper())
        return out or [ANY]
