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
    route `prefix/`, the detail route `prefix/{pk}/`, and one route per `@action` of the viewset.

    A nested router (drf-nested-routers: `NestedSimpleRouter(accounts, r'account', lookup='user')`) puts its routes
    under its parent's: `account/{user_pk}/` and whatever its parent sits under."""

    ROUTER_SUFFIX = 'Router'  # DefaultRouter, SimpleRouter, ExtendedSimpleRouter, NestedSimpleRouter...
    LOOKUP = '{pk}'
    ACTION = 'action'
    MAX_NESTING = 5  # nested routers under nested routers

    def __init__(self, workspace, values):
        self._workspace = workspace
        self._values = values
        self._registered = {}  # path -> {router name: [register call]}
        self._nested = {}  # path -> {router name: the NestedSimpleRouter(parent, prefix, lookup=...) call}

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
        owner = PythonSyntax.receiver(register)
        under = self._under(source, PythonSyntax.text(owner) if owner is not None else '')
        if under is None:
            return []
        handler = PythonSyntax.text(viewset)
        out = []
        for prefix in DjangoRegex.templates(v.text.strip('^$')):
            out += self._viewset_routes(source, viewset, under + prefix.strip('/'), handler)
        return out

    def _under(self, source, name, depth=0):
        """The path a router's routes sit under: '' for a router, 'account/{user_pk}/' for one nested under the
        `account` registration of another; None when a nested router's prefix is not a literal."""
        call = self._nesting(source).get(name)
        if call is None:
            return ''
        pos, kw = PythonSyntax.call_args(call)
        parent = pos[0] if pos else kw.get('parent_router')
        prefix = self._literal(source, pos[1] if len(pos) > 1 else kw.get('parent_prefix'))
        lookup = self._literal(source, kw.get('lookup')) or 'parent'
        if depth >= self.MAX_NESTING or parent is None or parent.type != 'identifier' or not prefix:
            return None
        above = self._under(source, PythonSyntax.text(parent), depth + 1)
        return None if above is None else f'{above}{prefix.strip("^$/")}/{{{lookup}_pk}}/'

    def _literal(self, source, node):
        if node is None:
            return ''
        v = self._values.resolve(node, Scope.at(source, node))[0]
        return v.text if v.is_literal and not Marker.names(v.text) else ''

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
        if source.path not in self._registered:
            self._registered[source.path], self._nested[source.path] = self._scan(source)
        return self._registered[source.path]

    def _nesting(self, source):
        self._read(source)
        return self._nested[source.path]

    def _scan(self, source):
        routers, nested = {}, {}
        for st in PythonSyntax.module_statements(source.root):
            for e in st.named_children if st.type == 'expression_statement' else ():
                self._statement(e, routers, nested)
        return routers, nested

    def _statement(self, e, routers, nested):
        if e.type == 'assignment':
            left, right = e.child_by_field_name('left'), e.child_by_field_name('right')
            is_call = left.type == 'identifier' and right is not None and right.type == 'call'
            if is_call and PythonSyntax.callee(right).endswith(self.ROUTER_SUFFIX):
                routers[PythonSyntax.text(left)] = []
                if PythonSyntax.call_args(right)[0] or 'parent_router' in PythonSyntax.call_args(right)[1]:
                    nested[PythonSyntax.text(left)] = right  # a router made from another: drf-nested-routers
        elif e.type == 'call' and PythonSyntax.callee(e) == 'register':
            owner = PythonSyntax.receiver(e)
            name = PythonSyntax.text(owner) if owner is not None else ''
            if name in routers:
                routers[name].append(e)
