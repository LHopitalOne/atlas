"""Django REST framework routers: the routes `router.register(prefix, ViewSet)` adds when `router.urls` is mounted."""

from typing import NamedTuple

from ......core.http import ANY
from ...scope import Scope
from ...syntax import PythonSyntax
from ...values import Marker
from .regex import DjangoRegex


class RouterRoute(NamedTuple):
    """One route a registered viewset serves, relative to where the router is mounted."""

    pattern: str
    methods: frozenset
    handler: str


class DrfRouters:
    """Finds routers (`router = DefaultRouter()`), what is registered on them, and the routes that makes: the list
    route `prefix/`, the detail route `prefix/{pk}/`, and one route per `@action` of the viewset."""

    ROUTER_SUFFIX = 'Router'  # DefaultRouter, SimpleRouter, ExtendedSimpleRouter, NestedSimpleRouter...
    LOOKUP = '{pk}'
    ACTION = 'action'

    def __init__(self, workspace, values):
        self._workspace = workspace
        self._values = values
        self._registered = {}  # path -> {router name: [register call]}

    def is_router(self, source, name):
        """Whether `name` is a module-level router of this file."""
        return name in self._read(source)

    def registrations(self, source, name):
        """The `name.register(...)` calls of this file's router `name`, in order."""
        return self._read(source).get(name, [])

    def routes(self, source, register) -> list[RouterRoute]:
        """The routes one `router.register(prefix, ViewSet)` call adds."""
        pos, kw = PythonSyntax.call_args(register)
        prefix_node = pos[0] if pos else kw.get('prefix')
        viewset = pos[1] if len(pos) > 1 else kw.get('viewset')
        if prefix_node is None or viewset is None:
            return []
        v = self._values.resolve(prefix_node, Scope.at(source, register))[0]
        if not v.is_literal or Marker.names(v.text):
            return []
        handler = PythonSyntax.text(viewset)
        out = []
        for prefix in DjangoRegex.templates(v.text.strip('^$')):
            out += self._viewset_routes(source, viewset, prefix.strip('/'), handler)
        return out

    def _viewset_routes(self, source, viewset, prefix, handler):
        anything = frozenset({ANY})
        out = [RouterRoute(f'{prefix}/', anything, handler), RouterRoute(f'{prefix}/{self.LOOKUP}/', anything, handler)]
        for detail, url_path, methods in self._actions(source, viewset):
            base = f'{prefix}/{self.LOOKUP}' if detail else prefix
            out.append(RouterRoute(f'{base}/{url_path}/', methods, f'{handler}.{url_path}'))
        return out

    def _actions(self, source, viewset):
        """(detail, url path, methods) of each `@action(...)` method of the viewset class."""
        found = self._workspace.names.expression(source, viewset)
        if not found or not found.is_class:
            return []
        body = found.node.child_by_field_name('body')
        out = []
        for st in body.named_children if body is not None else ():
            if st.type == 'decorated_definition':
                out += [a for d in st.named_children if d.type == 'decorator' for a in self._action(d, st)]
        return out

    def _action(self, decorator, definition):
        call = decorator.named_children[0] if decorator.named_children else None
        if call is None or call.type != 'call' or PythonSyntax.callee(call) != self.ACTION:
            return []
        _, kw = PythonSyntax.call_args(call)
        detail = PythonSyntax.text(kw.get('detail')) == 'True'
        name = PythonSyntax.name(definition.child_by_field_name('definition'))
        path_node = kw.get('url_path')
        url_path = PythonSyntax.text(path_node).strip('\'"') if path_node is not None else name
        methods = kw.get('methods')
        verbs = {PythonSyntax.text(m).strip('\'"').upper() for m in methods.named_children} if methods else {'GET'}
        return [(detail, url_path, frozenset(verbs))]

    def _read(self, source):
        found = self._registered.get(source.path)
        if found is None:
            found = self._registered[source.path] = self._scan(source)
        return found

    def _scan(self, source):
        routers = {}
        for st in PythonSyntax.module_statements(source.root):
            for e in st.named_children if st.type == 'expression_statement' else ():
                self._statement(e, routers)
        return routers

    def _statement(self, e, routers):
        if e.type == 'assignment':
            left, right = e.child_by_field_name('left'), e.child_by_field_name('right')
            is_call = left.type == 'identifier' and right is not None and right.type == 'call'
            if is_call and PythonSyntax.callee(right).endswith(self.ROUTER_SUFFIX):
                routers[PythonSyntax.text(left)] = []
        elif e.type == 'call' and PythonSyntax.callee(e) == 'register':
            owner = PythonSyntax.receiver(e)
            name = PythonSyntax.text(owner) if owner is not None else ''
            if name in routers:
                routers[name].append(e)
