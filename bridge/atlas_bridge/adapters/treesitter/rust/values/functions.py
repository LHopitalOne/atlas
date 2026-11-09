"""The crate's functions as values flow through them: which fn a call runs, its parameters and who calls it."""

from ..names import ItemPath
from ..syntax import RustSyntax


class CrateFunctions:
    """Free fns resolve through the workspace; associated fns (`Type::f(..)`, `Self::f(..)`) through the impls of
    their type. Only calls by path are followed: a method call `x.f(..)` would need the type of `x`."""

    def __init__(self, workspace):
        self._workspace = workspace
        self._methods = None  # (type name, fn name) -> [(file, fn node)] of the fns in impl blocks
        self._calls = None  # fn name -> [(file, call node)] of calls by path

    def target(self, file, call):
        """The crate fn a call by path runs, as (file, fn node), or None."""
        fnode = call.child_by_field_name('function')
        if fnode is None or fnode.type not in RustSyntax.NAMES:
            return None
        segs = ItemPath.segments(fnode)
        owner = self.impl_type(call) if len(segs) > 1 and segs[-2] == 'Self' else (segs[-2] if len(segs) > 1 else '')
        if not owner[:1].isupper():
            return self._workspace.resolve_fn(file, fnode)
        return self.method(file, owner, segs[-1])

    def method(self, file, owner, name):
        """The fn `name` of an impl of the type named `owner`, as (file, fn node), or None."""
        cands = self._index_methods().get((owner, name), [])
        return max(cands, key=lambda c: c[0] is file) if cands else None

    @staticmethod
    def params(fn) -> tuple[list[str], int]:
        """The names of a fn's parameters, and how many arguments come before them in a call by path: 1 for a
        `self` parameter (`Type::f(x, a)`), else 0."""
        node = fn.child_by_field_name('parameters')
        names, offset = [], 0
        for p in node.named_children if node is not None else ():
            if p.type == 'self_parameter':
                offset = 1
            elif p.type == 'parameter':
                names.append(RustSyntax.text(p.child_by_field_name('pattern')).replace('mut ', '').strip())
        return names, offset

    def arguments(self, file, fn, name):
        """(file, call node, argument node) for each call by path that passes parameter `name` of `fn`."""
        names, offset = self.params(fn)
        if name not in names:
            return []
        at, key, out = names.index(name) + offset, file.key(fn), []
        for cf, call in self._index_calls().get(RustSyntax.name(fn), []):
            target = self.target(cf, call)
            args = RustSyntax.args(call)
            if target is not None and target[0].key(target[1]) == key and at < len(args):
                out.append((cf, call, args[at]))
        return out

    @staticmethod
    def impl_type(node) -> str:
        """The name of the type whose impl block holds `node`, or ''."""
        impl = RustSyntax.ancestor(node, ('impl_item',))
        return ItemPath.last(impl.child_by_field_name('type')) if impl is not None else ''

    def _index_methods(self):
        if self._methods is None:
            self._methods = {}
            for f in self._workspace.files:
                for impl in f.nodes('impl'):
                    body = impl.child_by_field_name('body')
                    owner = ItemPath.last(impl.child_by_field_name('type'))
                    for fn in body.named_children if body is not None else ():
                        if fn.type == 'function_item':
                            self._methods.setdefault((owner, RustSyntax.name(fn)), []).append((f, fn))
        return self._methods

    def _index_calls(self):
        if self._calls is None:
            self._calls = {}
            for f in self._workspace.files:
                for c in f.nodes('call'):
                    fnode = c.child_by_field_name('function')
                    if fnode is not None and fnode.type in RustSyntax.NAMES:
                        segs = ItemPath.segments(fnode)
                        if segs:
                            self._calls.setdefault(segs[-1], []).append((f, c))
        return self._calls
