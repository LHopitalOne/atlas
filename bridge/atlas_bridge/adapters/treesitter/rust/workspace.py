"""A crate's Rust files with the indexes every collector shares: free functions, constants and let bindings."""

import os

from ..kit import Workspace
from .attributes import TestAttributes
from .bindings import LetBindings
from .names import ItemPath
from .source import RustFile
from .syntax import RustSyntax


class RustWorkspace(Workspace):
    """Resolves the names Rust code uses: a call's function, a constant, a let-bound variable."""

    PATH_ROOTS = frozenset({'crate', 'self', 'super'})
    METHOD_CONTAINERS = frozenset({'impl_item', 'trait_item'})

    def __init__(self, repo: str, sources: list):
        super().__init__(repo, [RustFile(s) for s in sources])

    def index(self):
        self._fns = {}  # name -> [(file, fn node)] of free functions (not methods)
        self._consts = {}  # name -> [(file, value node)] of consts and statics
        self._bindings = LetBindings()
        for f in self.sources:
            self._index_file(f)

    @property
    def files(self) -> list[RustFile]:
        return self.sources

    def resolve_fn(self, file, fnode):
        """The crate function a call's function expression names, as (file, fn node), or None."""
        if fnode is None or fnode.type not in RustSyntax.NAMES:
            return None
        segs = ItemPath.segments(fnode)
        if not segs:
            return None
        imported = file.imported(segs[0])
        if imported is not None:
            segs = imported.split('::') + segs[1:]
        name, mods = segs[-1], [s for s in segs[:-1] if s not in self.PATH_ROOTS]
        if mods and mods[-1][:1].isupper():  # Type::method: not a free function
            return None
        cands = self._fns.get(name, [])
        if mods:
            cands = [(cf, fn) for cf, fn in cands if self.module_of(cf, fn) == mods[-1]]
        if not cands:
            return None
        return max(cands, key=lambda c: self._rank(file, mods, c[0]))

    @staticmethod
    def module_of(file, fn):
        m = RustSyntax.ancestor(fn, ('mod_item',))
        return RustSyntax.name(m) if m is not None else file.module

    def const_value(self, file, node):
        """The value of the const or static a name refers to, as (file, value node), or None."""
        node = RustSyntax.unwrap(node)
        if node is None or node.type not in RustSyntax.NAMES:
            return None
        return self.const_named(file, ItemPath.segments(node)[-1])

    def const_named(self, file, name):
        """The value of the const or static called `name` (the same file's first), as (file, value node), or None."""
        cands = self._consts.get(name, [])
        if not cands:
            return None
        return max(cands, key=lambda c: c[0] is file)

    def binding(self, file, node):
        """The value of the latest `let` of this identifier before it, or None."""
        return self._bindings.value(file, node)

    def binding_named(self, file, name, at):
        """The value of the latest `let <name>` before node `at` in its function, or None."""
        return self._bindings.named(file, name, at)

    @staticmethod
    def in_test(node):
        return TestAttributes.encloses(node)

    def is_test(self, source, node=None) -> bool:
        return source.tested or (node is not None and self.in_test(node))

    @staticmethod
    def _rank(file, mods, candidate):
        """Prefer the same file, then a path naming the call's modules, then the nearest folder."""
        return (
            candidate is file,
            sum(m in candidate.parts for m in mods),
            len(os.path.commonprefix([candidate.path, file.path])),
        )

    def _index_file(self, f):
        for fn in f.nodes('fn'):
            parent = fn.parent
            if (
                parent is not None
                and parent.type == 'declaration_list'
                and parent.parent.type in self.METHOD_CONTAINERS
            ):
                continue
            self._fns.setdefault(RustSyntax.name(fn), []).append((f, fn))
        for c in f.nodes('const'):
            v = c.child_by_field_name('value')
            if v is not None:
                self._consts.setdefault(RustSyntax.name(c), []).append((f, v))
