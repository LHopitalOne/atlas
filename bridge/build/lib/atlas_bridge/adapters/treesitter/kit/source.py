"""One source file: its bytes, grammar and (parsed on first use) syntax tree."""

import tree_sitter as ts

from .grammar import Grammar
from .syntax import Syntax


class SourceFile:
    def __init__(self, path: str, data: bytes, grammar: Grammar, test: bool = False):
        self.path = path
        self.data = data
        self.grammar = grammar
        self.test = test  # the path alone says this is test or tooling code
        self._tree = None

    @property
    def root(self):
        if self._tree is None:
            self._tree = self.grammar.parse(self.data)
        return self._tree.root_node

    def mentions(self, *needles: bytes) -> bool:
        """A cheap check before parsing: does the file contain any of these bytes?"""
        return any(n in self.data for n in needles)

    def captures(self, query_source: str):
        """{capture name: [nodes]} for a query over the whole file."""
        return ts.QueryCursor(self.grammar.query(query_source)).captures(self.root)

    def matches(self, query_source: str):
        """[(pattern index, {capture name: [nodes]})] for a query over the whole file, match by match."""
        return ts.QueryCursor(self.grammar.query(query_source)).matches(self.root)

    text = staticmethod(Syntax.text)
    line = staticmethod(Syntax.line)
