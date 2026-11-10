"""The calls that fill in a request helper's parameters: calls of the helper by name, through a module namespace
(`api.get(...)` after `import * as api from './api'`), through `this` in its class, and calls of a parameter that
stands for the helper (`submit(api.patch, '/x')` where `submit(send, url) { send({ url }) }`)."""

from dataclasses import dataclass

from ..linker import ModuleLinker
from ..syntax.functions import Functions
from ..syntax.nodes import JsSyntax
from ..syntax.params import Params


@dataclass(frozen=True)
class Handoff:
    """A call that hands the helper to another function (`call`), and a call of the parameter that receives it in
    that function (`inner`, in `module`): the helper is called there, with the outer call's arguments."""

    call: object
    module: object  # JsModule of the function that receives the helper
    inner: object
    function: str  # the name of that function


class Callers:
    """Finds the calls of an open request's function across the workspace."""

    MAX_SITES = 200  # calls one open request is settled at
    CALLS = frozenset({'call_expression', 'new_expression'})
    CONSTRUCTOR = 'constructor'

    def __init__(self, workspace, modules):
        self._workspace = workspace
        self._modules = modules  # source -> JsModule, shared with the forwarder
        self._by_path = {s.path: s for s in workspace.sources}
        self._linker = ModuleLinker(workspace.sources, None)  # only to name the files imports lead to

    def of(self, open_) -> tuple[list, list]:
        """([(module, call)] of the function, [(module, Handoff)] of calls that pass it to another function)."""
        direct, handoffs = [], []
        for source in self._workspace.sources:
            if not source.mentions(self.name_of(open_).encode()):
                continue
            module = self._modules(source)
            if not self._may_call(module, open_):
                continue
            for call in JsSyntax.walk(source.root, self.CALLS):
                if self._calls(module, open_, call):
                    direct.append((module, call))
                elif not open_.method_of_class:
                    handoffs += [(module, h) for h in self._handoffs(module, open_, call)]
        return direct[: self.MAX_SITES], handoffs[: self.MAX_SITES]

    def _may_call(self, module, open_):
        """The file may name the function: its own file, or one that imports it by name or its whole module."""
        if module.path == open_.path:
            return True
        if self._constructs(open_):
            return self._imports(module, open_)
        if open_.method_of_class:
            return False
        sources = module.imports.namespace_sources()
        return self._imports(module, open_) or any(ModuleLinker.may_name(module.path, s, open_.path) for s in sources)

    def _calls(self, module, open_, call):
        if call.type == 'new_expression' or self._constructs(open_):
            ctor = JsSyntax.unwrap(call.child_by_field_name('constructor'))
            return self._constructs(open_) and ctor is not None and self._names(module, open_, ctor)
        fn = JsSyntax.unwrap(call.child_by_field_name('function'))
        if open_.method_of_class:
            ok = fn.type == 'member_expression' and JsSyntax.text(fn.child_by_field_name('object')) == 'this'
            ok = ok and JsSyntax.text(fn.child_by_field_name('property')) == open_.function
            return ok and Functions.enclosing(call)[1] == open_.owner
        return self._names(module, open_, fn)

    def _names(self, module, open_, node):
        """`node` names the open request's function: by name in its file or a file that imports it, or as a
        member of a namespace of its file."""
        if node is None:
            return False
        if node.type == 'identifier':
            if JsSyntax.text(node) != self.name_of(open_):
                return False
            return module.path == open_.path or self._imports(module, open_)
        if node.type != 'member_expression' or JsSyntax.text(node.child_by_field_name('property')) != self.name_of(
            open_
        ):
            return False
        source = module.imports.namespace(JsSyntax.text(node.child_by_field_name('object')))
        return source is not None and ModuleLinker.may_name(module.path, source, open_.path)

    @classmethod
    def _imports(cls, module, open_):
        """The module imports the open request's function (or the class it constructs) from its file (not a name
        of a package that has the same name)."""
        imported = module.imports.get(cls.name_of(open_))
        return imported is not None and ModuleLinker.may_name(module.path, imported[0], open_.path)

    @classmethod
    def _constructs(cls, open_):
        """The open request is a constructor's: `new <class>(...)` fills it in."""
        return open_.method_of_class and open_.function == cls.CONSTRUCTOR

    @classmethod
    def name_of(cls, open_):
        """The name its callers call it by: the class of a constructor, else the function."""
        return open_.owner if cls._constructs(open_) else open_.function

    def _handoffs(self, module, open_, call):
        """A call that passes the function itself as an argument, and the calls of the parameter it lands in."""
        args = JsSyntax.args(call)
        given = [i for i, a in enumerate(args) if self._refers(module, open_, JsSyntax.unwrap(a))]
        if not given:
            return []
        found = self._function(module, JsSyntax.unwrap(call.child_by_field_name('function')))
        if found is None:
            return []
        target, fn = found
        params = {p.index: p.name for p in Params.of(fn) if p.name}
        name = Functions.name(fn)
        return [
            Handoff(call, target, c, name) for i in given if i in params for c in self._calls_of(target, fn, params[i])
        ]

    def _refers(self, module, open_, node):
        """`node` is the function itself (not a call of it): an imported name, a namespace member, or a function of
        the same file."""
        if node is None or not self._names(module, open_, node):
            return False
        if node.type == 'identifier' and module.path == open_.path and module.imports.get(open_.function) is None:
            bound = JsSyntax.unwrap(module.scopes.lookup(node, open_.function))
            return bound is not None and bound.type in Functions.FUNCTIONS
        return True

    def _function(self, module, callee):
        """(module, function node) a callee names: a function of the file, or one another file of the repository
        exports (by name, or as a member of its namespace); None when that cannot be told."""
        if callee is None:
            return None
        if callee.type == 'identifier':
            name = JsSyntax.text(callee)
            bound = JsSyntax.unwrap(module.scopes.lookup(callee, name))
            if bound is not None:
                return (module, bound) if bound.type in Functions.FUNCTIONS else None
            imported = module.imports.get(name)
            return self._exported(module, *imported) if imported is not None else None
        if callee.type != 'member_expression':
            return None
        source = module.imports.namespace(JsSyntax.text(callee.child_by_field_name('object')))
        name = JsSyntax.text(callee.child_by_field_name('property'))
        return self._exported(module, source, name) if source is not None else None

    def _exported(self, module, source, name):
        path = self._path(module.path, source)
        target = self._modules(self._by_path[path]) if path is not None else None
        fn = JsSyntax.unwrap(target.exports.value(name)) if target is not None else None
        return (target, fn) if fn is not None and fn.type in Functions.FUNCTIONS else None

    def _path(self, importer, source):
        """The file an import names: the one a relative import leads to, or the only file an alias may name."""
        if source.startswith('.'):
            return self._linker.path(importer, source)
        found = [p for p in self._by_path if ModuleLinker.may_name(importer, source, p)]
        return found[0] if len(found) == 1 else None

    @staticmethod
    def _calls_of(module, fn, name):
        """The calls of parameter `name` inside `fn` (a name the function binds again is another value)."""
        params = fn.child_by_field_name('parameters') or fn.child_by_field_name('parameter')
        out = []
        for call in JsSyntax.walk(fn, {'call_expression'}):
            callee = JsSyntax.unwrap(call.child_by_field_name('function'))
            if callee.type != 'identifier' or JsSyntax.text(callee) != name:
                continue
            binding = module.scopes.binding(callee, name)
            if binding is not None and params is not None and JsSyntax.contains(params, binding.node):
                out.append(call)
        return out
