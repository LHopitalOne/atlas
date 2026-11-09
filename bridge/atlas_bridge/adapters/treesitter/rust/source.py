"""One Rust file with what it says about itself: its module name, imports, framework and method chains."""

import os
from functools import cached_property

from ..kit import SourceFile
from .attributes import TestAttributes
from .syntax import RustSyntax
from .uses import UseTree


class RustFile(SourceFile):
    """A source file, indexed on first use: the nodes every collector starts from (in source order), the names
    its `use` declarations bring in, and for each call the call made on its result (`a()` -> `a().b()`). Nothing
    is parsed until a collector asks."""

    QUERY = """
    (function_item) @fn
    (call_expression) @call
    (impl_item) @impl
    (attribute_item) @attr
    (const_item) @const
    (static_item) @const
    (use_declaration) @use
    (struct_item) @struct
    (struct_expression) @init
    """
    ENTRY_STEMS = ('mod', 'lib', 'main')  # files named after their folder's module
    DEFAULT_FRAMEWORK = 'axum'
    ACTIX = 'actix'  # the framework of a file that uses actix_web

    def __init__(self, source: SourceFile):
        super().__init__(source.path, source.data, source.grammar, source.test)
        stem = os.path.splitext(os.path.basename(self.path))[0]
        self._module = os.path.basename(os.path.dirname(self.path)) if stem in self.ENTRY_STEMS else stem
        self._parts = frozenset(os.path.splitext(self.path)[0].replace('\\', '/').split('/'))

    @property
    def module(self) -> str:
        """The module the file is: its stem, or its folder's name for mod.rs, lib.rs and main.rs."""
        return self._module

    @property
    def parts(self) -> frozenset:
        """The folder and stem names of the file's path."""
        return self._parts

    @property
    def framework(self) -> str:
        """'actix' when the file uses actix_web, else 'axum'."""
        return self._imports[1]

    @property
    def tested(self) -> bool:
        """Test code by path or by an inner `#![cfg(test)]`."""
        return self.test or self._file_test

    def nodes(self, capture: str) -> list:
        """The nodes of one capture of QUERY, in source order: 'fn', 'call', 'impl', 'attr', 'const', 'use',
        'struct' (declarations) or 'init' (struct expressions)."""
        return self._nodes.get(capture, [])

    def key(self, node):
        """Identifies a node across the repository."""
        return (self.path, node.start_byte, node.end_byte, node.type)

    def imported(self, name, default=None):
        """The full path a `use` declaration gives a local name."""
        return self._imports[0].get(name, default)

    def outer_call(self, call):
        """The call made on this call's result, or None."""
        return self._outer.get(self.key(call))

    def has_outer_call(self, call):
        return self.key(call) in self._outer

    def span(self, a, b):
        """The source text from the start of `a` to the end of `b`."""
        return self.data[a.start_byte : b.end_byte].decode('utf-8', 'replace')

    @cached_property
    def _nodes(self) -> dict:
        """{capture: [node]}, each list sorted by position (the query cursor does not promise an order)."""
        found = self.captures(self.QUERY)
        return {k: sorted(v, key=lambda n: (n.start_byte, -n.end_byte)) for k, v in found.items()}

    @cached_property
    def _imports(self) -> tuple:
        """({local name: full path} from the `use` declarations, framework). A later `use` overrides an earlier."""
        uses, framework = {}, self.DEFAULT_FRAMEWORK
        for u in self.nodes('use'):
            arg = u.child_by_field_name('argument')
            if arg is not None:
                uses.update(UseTree.read(arg))
                if self.text(arg).lstrip(':').startswith(self.ACTIX):
                    framework = self.ACTIX
        return uses, framework

    @cached_property
    def _outer(self) -> dict:
        """{call key: the call made on its result}."""
        outer = {}
        for c in self.nodes('call'):
            fn = RustSyntax.method(c)
            if fn is not None:
                value = RustSyntax.unwrap(fn.child_by_field_name('value'))
                if value is not None and value.type == 'call_expression':
                    outer[self.key(value)] = c
        return outer

    @cached_property
    def _file_test(self) -> bool:
        """`#![cfg(test)]`: the whole file is test code."""
        return any(
            a.type == 'inner_attribute_item' and any(TestAttributes.is_test(self.text(x)) for x in a.named_children)
            for a in self.root.named_children
        )
