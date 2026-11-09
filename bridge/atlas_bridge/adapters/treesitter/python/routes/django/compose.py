"""Composing a URLconf: each entry's pattern prefixed by the include() chain that reaches it."""

from ...scope import Scope
from ...syntax import PythonSyntax
from ...values import Marker, Value
from ..converters import FlaskPath
from .loops import BoundText
from .modules import IncludedModules
from .regex import DjangoRegex


class Composition:
    """What one composition run produced: routes, and the files it reached through include()."""

    def __init__(self):
        self._routes = []
        self._included = set()

    def add_route(self, route):
        self._routes.append(route)

    def include(self, path):
        self._included.add(path)

    @property
    def routes(self):
        return list(self._routes)

    @property
    def included(self):
        return frozenset(self._included)


class UrlComposer:
    """Walks a URLconf's entries, expanding include() with the prefixes above it, and builds the leaf routes.

    A route a helper declares is placed at the helper's call, with the view the call passes for the helper's view
    parameter, and serves the HTTP methods the call names as keywords (`api_route('users', GET=list_users,
    POST=add_user)`: one route per method, each with its view)."""

    MAX_ALTS = DjangoRegex.MAX_ALTS

    def __init__(self, route, names, values, entries, views, routers):
        self._route = route  # the route factory: (source, line, path, methods, handler, name) -> Route
        self._names = names  # NameLookup, for the modules include('dotted.name') names
        self._values = values
        self._entries = entries  # UrlEntries
        self._views = views  # ViewMethods
        self._routers = routers  # DrfRouters
        self._modules = IncludedModules(names, values)
        self._text = BoundText(values)

    def compose(self, source, name) -> Composition:
        """Every route a module-level URL list composes to, with no prefix."""
        out = Composition()
        ref = self._entries.list_ref(source, name)
        if ref is not None:
            for entry in self._entries.list_entries(ref[0], ref[1]):
                self._entry(entry, [''], frozenset(), out, False)
        return out

    def compose_mounted(self, source, regex) -> Composition:
        """Every route of a module's `urlpatterns`, mounted at a regex (a plugin's URL config)."""
        out = Composition()
        for entry in self._entries.module_entries(source):
            self._entry(entry, DjangoRegex.templates(regex), frozenset(), out, True)
        return out

    def _entry(self, entry, prefixes, stack, out, nested):
        pat, binding = entry.call, entry.binding
        where, declaring = entry.declared
        key = (where.path, declaring.start_byte)
        if key in stack:
            return
        if nested:
            out.include(where.path)
        if entry.kind == entry.ROUTER:
            self._router_entry(entry.source, pat, prefixes, out)
            return
        pos, kw = PythonSyntax.call_args(pat)
        view = pos[1] if len(pos) > 1 else kw.get('view')
        full = [p + a for p in prefixes for a in self._patterns(entry, pos, kw)][: self.MAX_ALTS]
        if view is None:
            return
        argument = binding.argument(view) if binding is not None else None
        view_source, view = argument if argument is not None else (entry.source, view)
        if view.type == 'call' and PythonSyntax.callee(view) == 'include':
            inner = binding if argument is None else None
            for child in self._included(view_source, view, inner):
                self._entry(child, full, stack | {key}, out, True)
            return
        name = self._route_name(entry.source, kw.get('name'), binding)
        line = PythonSyntax.line(declaring)
        for methods, handler in self._served(entry, view_source, view):
            for p in full:
                out.add_route(self._route(where, line, '/' + p, methods, handler, name))

    def _served(self, entry, source, view):
        """[(methods, handler)] of an entry: one per HTTP method its helper call names, else its view's."""
        keyed = self._views.keyword_views(entry.site.call) if entry.site is not None else []
        if keyed:
            return [(frozenset({method}), handler) for method, handler in keyed]
        handler, methods = self._views.handler_and_methods(source, view)
        return [(methods, handler)]

    def _router_entry(self, source, register, prefixes, out):
        line = PythonSyntax.line(register)
        for r in self._routers.routes(source, register):
            for p in prefixes:
                out.add_route(self._route(source, line, '/' + p + r.pattern, r.methods, r.handler, ''))

    def _patterns(self, entry, pos, kw):
        """The path templates one entry's pattern stands for: a path() route, or a regex's alternatives. A route
        helper's parameters take the call's literal arguments, and a loop's variable each text the loop gives it.
        Unresolved, it is '{param}', or nothing in a loop."""
        source, pat, binding = entry.source, entry.call, entry.binding
        node = pos[0] if pos else kw.get('route', kw.get('regex'))
        loop = binding is not None and binding.is_loop
        if loop and node is not None and self._text.mentions(node, binding.values):
            text = self._text.text(Scope.at(source, pat), node, binding.values)
            return [] if text is None else self._templates(pat, text)
        v = self._values.resolve(node, Scope.at(source, pat))[0] if node is not None else None
        text = Marker.fill(v.text, binding.values if binding is not None else {}) if v is not None else ''
        if v is None or not v.is_known or Marker.is_unresolved(text):
            return [] if loop else ['{param}']
        return self._templates(pat, text)

    @staticmethod
    def _templates(pat, text):
        if PythonSyntax.callee(pat) == 'path':
            return [FlaskPath.template(text)]
        return DjangoRegex.templates(text)

    def _included(self, source, view, binding):
        """The entries an include() brings in: a list expression, or a module its argument names."""
        ipos, ikw = PythonSyntax.call_args(view)
        arg = ipos[0] if ipos else ikw.get('arg')
        if arg is not None and arg.type == 'tuple' and arg.named_children:
            arg = arg.named_children[0]
        if arg is None:
            return ()
        listed = [] if arg.type == 'string' else list(self._entries.entries_of(source, arg, binding))
        if listed:
            return listed
        given = binding.values if binding is not None else {}
        return self._entries.module_entries(self._modules.module(Scope.at(source, view), arg, given))

    def _route_name(self, source, node, binding):
        """The literal `name=` of an entry, filling builder parameters from the call that built the list."""
        if node is None:
            return ''
        v = self._values.resolve(node, Scope(source, binding.func if binding else None, None))[0]
        if v.is_param:
            v = Value(v.text)
        name = Marker.fill(v.text, binding.values if binding else {})
        return name if v.is_literal and not Marker.is_unresolved(name) and '{' not in name else ''
