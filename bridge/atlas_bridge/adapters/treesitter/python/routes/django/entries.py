"""The path()/re_path()/url() entries a URL list expression contains, followed through names, imports and the
functions that build lists."""

from typing import NamedTuple

from ...scope import Scope
from ...syntax import PythonSyntax
from ...values import Marker
from ...workspace import NameLookup


class ListBinding(NamedTuple):
    """Inside a function that builds a URL list: the function, and {parameter: literal text} from its call."""

    func: object
    values: dict


class Entry(NamedTuple):
    """One path()/re_path()/url() call, the file it is in, and the binding it was built under (or None)."""

    source: object
    call: object
    binding: ListBinding | None


class UrlEntries:
    """Walks URL list expressions down to their entries: list literals, `+`, `*splat`, names of lists (in this module
    or imported), `module.LIST`, `patterns('', ...)`, `list(...)`, and calls of functions that return lists."""

    MAX_DEPTH = 30
    CONTAINERS = frozenset({'list', 'tuple', 'expression_list', 'set', 'list_splat', 'parenthesized_expression'})
    ENTRIES = frozenset({'path', 're_path', 'url'})

    def __init__(self, workspace, values, lists):
        self._workspace = workspace
        self._values = values
        self._lists = lists  # UrlLists

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
            yield from self.entries_of(source, c.node, None, seen | {key}, depth + 1)

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
            yield from self._module_attribute(source, node, seen, depth)

    def _name(self, source, node, binding, seen, depth):
        name = PythonSyntax.text(node)
        if binding is not None:
            local = self._workspace.locals.assignments_in(source, binding.func).get(name)
            if local:
                yield from self.entries_of(source, local[-1].value, binding, seen, depth + 1)
                return
        ref = self.list_ref(source, name)
        if ref is not None:
            yield from self.list_entries(ref[0], ref[1], seen, depth)

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
        else:  # a function that builds the list: include(create_group_urls('prefix'))
            yield from self._builder(source, node, pos, kw, seen, depth)

    def _builder(self, source, node, pos, kw, seen, depth):
        found = self._workspace.names.expression(source, node.child_by_field_name('function'))
        if not found or not found.is_function or (found.source.path, found.node.start_byte) in seen:
            return
        func = found.node
        binding = ListBinding(func, self._literal_arguments(source, node, func, pos, kw))
        key = (found.source.path, func.start_byte)
        for r in PythonSyntax.body_nodes(func.child_by_field_name('body')):
            if r.type == 'return_statement' and r.named_children:
                yield from self.entries_of(found.source, r.named_children[0], binding, seen | {key}, depth + 1)

    def _literal_arguments(self, source, call, func, pos, kw):
        """{parameter: text} of the arguments of a builder call that are plain literals."""
        params = PythonSyntax.params(func)
        values = {params[i][0]: a for i, a in enumerate(pos[: len(params)])}
        values.update(kw)
        bound = {}
        scope = Scope.at(source, call)
        for k, a in values.items():
            v = self._values.resolve(a, scope)[0]
            if v.is_literal and not Marker.names(v.text):
                bound[k] = v.text
        return bound
