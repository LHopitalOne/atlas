"""The path()/re_path()/url() entries a URL list expression contains, followed through names, imports and the
functions that build lists."""

from typing import NamedTuple

from ...scope import Scope
from ...syntax import PythonSyntax
from ...values import Marker
from ...workspace import NameLookup
from .loops import LoopValues


class ListBinding(NamedTuple):
    """Inside a function that builds a URL list: the function, and {parameter: literal text} from its call. Inside a
    module-level `for` loop: no function, and {loop variable: one literal text the loop gives it}."""

    func: object
    values: dict

    @property
    def is_loop(self):
        return self.func is None


class Site(NamedTuple):
    """Where a route helper is called in a URL list: the file and the call."""

    source: object
    call: object


class Entry(NamedTuple):
    """One path()/re_path()/url() call (or a DRF `router.register()` call, kind ROUTER), the file it is in, the
    binding it was built under (or None), and the route helper call that declares it (or None)."""

    PATH, ROUTER = 'path', 'router'

    source: object
    call: object
    binding: ListBinding | None
    kind: str = PATH
    site: Site | None = None

    @property
    def declared(self):
        """(file, node) of what declares the route: the route helper call, else the path() call itself."""
        return (self.site.source, self.site.call) if self.site is not None else (self.source, self.call)


class UrlEntries:
    """Walks URL list expressions down to their entries: list literals, `+`, `*splat`, names of lists (in this module
    or imported), `module.LIST`, `router.urls`, `patterns('', ...)`, `list(...)`, and calls of functions that return
    lists.

    A function that returns one path()/re_path() call (or a call of another such function) is a route helper: each
    call of it in a URL list declares the route there, its parameters bound to the call's literal arguments. Lists
    extended in a module-level `for` loop are read once per literal text the loop gives its variable.
    """

    MAX_DEPTH = 30
    CONTAINERS = frozenset({'list', 'tuple', 'expression_list', 'set', 'list_splat', 'parenthesized_expression'})
    ENTRIES = frozenset({'path', 're_path', 'url'})

    def __init__(self, workspace, values, lists, routers):
        self._workspace = workspace
        self._values = values
        self._lists = lists  # UrlLists
        self._routers = routers  # DrfRouters
        self._loops = LoopValues(workspace, values)

    def list_ref(self, source, name, depth=0):
        """(file, name) of the module-level list a name refers to, following `from x import name`; or None."""
        if name in self._lists.lists_in(source):
            return source, name
        if depth < NameLookup.MAX_IMPORTS:
            found = self._workspace.names.imported_from(source, name)
            if found is not None:
                return self.list_ref(found[0], found[1], depth + 1)
        return None

    def list_entries(self, source, name, seen=frozenset(), depth=0):
        """Entries of a module-level list."""
        key = (source.path, name)
        if key in seen:
            return
        for c in self._lists.lists_in(source).get(name, ()):
            bindings = [None] if c.loop is None else [ListBinding(None, v) for v in self._loops.values(source, c.loop)]
            for binding in bindings:
                yield from self.entries_of(source, c.node, binding, seen | {key}, depth + 1)

    def module_entries(self, source):
        """Entries of a module's `urlpatterns`, or nothing when it has none."""
        ref = self.list_ref(source, 'urlpatterns') if source is not None else None
        return self.list_entries(ref[0], ref[1]) if ref else ()

    def entries_of(self, source, node, binding, seen=frozenset(), depth=0):
        """[Entry] of a URL list expression."""
        if node is None or depth > self.MAX_DEPTH:
            return
        t = node.type
        if t in self.CONTAINERS:
            for c in node.named_children:
                yield from self.entries_of(source, c, binding, seen, depth + 1)
        elif t == 'binary_operator':
            yield from self.entries_of(source, node.child_by_field_name('left'), binding, seen, depth + 1)
            yield from self.entries_of(source, node.child_by_field_name('right'), binding, seen, depth + 1)
        elif t == 'call':
            yield from self._call(source, node, binding, seen, depth)
        elif t == 'identifier':
            yield from self._name(source, node, binding, seen, depth)
        elif t == 'attribute':
            yield from self._attribute(source, node, seen, depth)

    def _name(self, source, node, binding, seen, depth):
        name = PythonSyntax.text(node)
        if binding is not None and not binding.is_loop:
            local = self._workspace.locals.assignments_in(source, binding.func).get(name)
            if local:
                yield from self.entries_of(source, local[-1].value, binding, seen, depth + 1)
                return
        ref = self.list_ref(source, name)
        if ref is not None:
            yield from self.list_entries(ref[0], ref[1], seen, depth)

    def _attribute(self, source, node, seen, depth):
        """`router.urls` of a DRF router in this file, else `module.LIST`."""
        owner = node.child_by_field_name('object')
        name = PythonSyntax.text(owner) if owner.type == 'identifier' else ''
        if PythonSyntax.text(node.child_by_field_name('attribute')) == 'urls' and self._routers.is_router(source, name):
            for register in self._routers.registrations(source, name):
                yield Entry(source, register, None, Entry.ROUTER)
            return
        yield from self._module_attribute(source, node, seen, depth)

    def _module_attribute(self, source, node, seen, depth):
        found = self._workspace.names.expression(source, node.child_by_field_name('object'))
        module_file = self._workspace.names.locate(found.ref) if found and found.is_module else None
        attr = PythonSyntax.text(node.child_by_field_name('attribute'))
        ref = self.list_ref(module_file, attr) if module_file is not None else None
        if ref is not None:
            yield from self.list_entries(ref[0], ref[1], seen, depth)

    def _call(self, source, node, binding, seen, depth):
        name = PythonSyntax.callee(node)
        pos, kw = PythonSyntax.call_args(node)
        if name in self.ENTRIES and (len(pos) >= 2 or 'view' in kw):
            yield Entry(source, node, binding)
        elif name == 'patterns':
            for a in pos[1:]:
                yield from self.entries_of(source, a, binding, seen, depth + 1)
        elif name in ('list', 'tuple') and pos:
            yield from self.entries_of(source, pos[0], binding, seen, depth + 1)
        else:  # a function that builds the list: include(create_group_urls('prefix')), or a route helper
            yield from self._builder(source, node, (pos, kw), binding, seen, depth)

    def _builder(self, source, node, args, outer, seen, depth):
        found = self._workspace.names.expression(source, node.child_by_field_name('function'))
        if not found or not found.is_function or (found.source.path, found.node.start_byte) in seen:
            return
        func = found.node
        binding = ListBinding(func, self._literal_arguments(source, node, func, args, outer))
        key = (found.source.path, func.start_byte)
        for r in PythonSyntax.body_nodes(func.child_by_field_name('body')):
            if r.type == 'return_statement' and r.named_children:
                returned = r.named_children[0]
                for entry in self.entries_of(found.source, returned, binding, seen | {key}, depth + 1):
                    declared = entry.declared
                    helper = declared[0].path == found.source.path and self._same(declared[1], returned)
                    yield entry._replace(site=Site(source, node)) if helper else entry

    @staticmethod
    def _same(a, b):
        return (a.start_byte, a.end_byte) == (b.start_byte, b.end_byte)

    def _literal_arguments(self, source, call, func, args, outer):
        """{parameter: text} of the arguments of a builder call that are plain literals, or the outer builder's
        parameters that its own call bound to literals."""
        pos, kw = args
        params = PythonSyntax.params(func)
        values = {params[i][0]: a for i, a in enumerate(pos[: len(params)])}
        values.update(kw)
        given = outer.values if outer is not None and not outer.is_loop else {}
        bound = {}
        scope = Scope.at(source, call)
        for k, a in values.items():
            v = self._values.resolve(a, scope)[0]
            text = Marker.fill(v.text, given)
            if v.is_known and not Marker.is_unresolved(text):
                bound[k] = text
        return bound
