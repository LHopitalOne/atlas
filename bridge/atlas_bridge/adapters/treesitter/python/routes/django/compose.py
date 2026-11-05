"""Composing a URLconf: each entry's pattern prefixed by the include() chain that reaches it."""

from ...scope import Scope
from ...syntax import PythonSyntax
from ...values import Marker, Value
from ..converters import FlaskPath
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
    """Walks a URLconf's entries, expanding include() with the prefixes above it, and builds the leaf routes."""

    MAX_ALTS = DjangoRegex.MAX_ALTS

    def __init__(self, route, names, values, entries, views):
        self._route = route  # the route factory: (source, line, path, methods, handler, name) -> Route
        self._names = names  # NameLookup, for the modules include('dotted.name') names
        self._values = values
        self._entries = entries  # UrlEntries
        self._views = views  # ViewMethods

    def compose(self, source, name) -> Composition:
        """Every route a module-level URL list composes to, with no prefix."""
        out = Composition()
        ref = self._entries.list_ref(source, name)
        if ref is not None:
            for entry in self._entries.list_entries(ref[0], ref[1]):
                self._entry(entry, [''], frozenset(), out, False)
        return out

    def _entry(self, entry, prefixes, stack, out, nested):
        source, pat, binding = entry
        key = (source.path, pat.start_byte)
        if key in stack:
            return
        if nested:
            out.include(source.path)
        pos, kw = PythonSyntax.call_args(pat)
        view = pos[1] if len(pos) > 1 else kw.get('view')
        full = [p + a for p in prefixes for a in self._patterns(source, pat, pos, kw)][: self.MAX_ALTS]
        if view is None:
            return
        if view.type == 'call' and PythonSyntax.callee(view) == 'include':
            for child in self._included(source, pat, view, binding):
                self._entry(child, full, stack | {key}, out, True)
            return
        handler, methods = self._views.handler_and_methods(source, view)
        name = self._route_name(source, kw.get('name'), binding)
        line = PythonSyntax.line(pat)
        for p in full:
            out.add_route(self._route(source, line, '/' + p, methods, handler, name))

    def _patterns(self, source, pat, pos, kw):
        """The path templates one entry's pattern stands for: a path() route, or a regex's alternatives."""
        node = pos[0] if pos else kw.get('route', kw.get('regex'))
        v = self._values.resolve(node, Scope.at(source, pat))[0] if node is not None else None
        if v is None or not v.is_literal or Marker.names(v.text):
            return ['{param}']
        if PythonSyntax.callee(pat) == 'path':
            return [FlaskPath.template(v.text)]
        return DjangoRegex.templates(v.text)

    def _included(self, source, pat, view, binding):
        """The entries an include() brings in: a module named by a string, or a list expression."""
        ipos, ikw = PythonSyntax.call_args(view)
        arg = ipos[0] if ipos else ikw.get('arg')
        if arg is not None and arg.type == 'tuple' and arg.named_children:
            arg = arg.named_children[0]
        if arg is None:
            return ()
        if arg.type == 'string':
            dotted = self._values.string(arg, Scope.at(source, pat)).text
            return self._entries.module_entries(self._names.dotted_module(dotted))
        return self._entries.entries_of(source, arg, binding)

    def _route_name(self, source, node, binding):
        """The literal `name=` of an entry, filling builder parameters from the call that built the list."""
        if node is None:
            return ''
        v = self._values.resolve(node, Scope(source, binding.func if binding else None, None))[0]
        if v.is_param:
            v = Value(v.text)
        name = Marker.fill(v.text, binding.values if binding else {})
        return name if v.is_literal and not Marker.is_unresolved(name) and '{' not in name else ''
