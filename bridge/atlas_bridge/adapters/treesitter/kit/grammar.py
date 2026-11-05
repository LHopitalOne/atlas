"""tree-sitter grammars: which one reads a file, loading it once, parsing and compiling queries with it."""

import os

import tree_sitter as ts

from ....core.errors import ParserUnavailableError


class Grammar:
    """One tree-sitter language. Grammars are loaded on first use and shared; a missing grammar package raises
    ParserUnavailableError instead of ImportError."""

    BY_EXTENSION = {
        '.py': 'python',
        '.rs': 'rust',
        '.js': 'javascript',
        '.mjs': 'javascript',
        '.cjs': 'javascript',
        '.jsx': 'javascript',
        '.ts': 'typescript',
        '.tsx': 'tsx',
    }
    _loaded: dict = {}

    def __init__(self, name: str):
        self.name = name
        self.language = self._load(name)
        self._queries = {}

    @classmethod
    def named(cls, name: str) -> 'Grammar':
        if name not in cls._loaded:
            cls._loaded[name] = cls(name)
        return cls._loaded[name]

    @classmethod
    def for_path(cls, path: str) -> 'Grammar | None':
        name = cls.BY_EXTENSION.get(os.path.splitext(path)[1])
        return cls.named(name) if name else None

    def parse(self, source: bytes):
        return ts.Parser(self.language).parse(source)

    def query(self, source: str):
        """A compiled query, cached per grammar: the same query text is compiled once."""
        if source not in self._queries:
            self._queries[source] = ts.Query(self.language, source)
        return self._queries[source]

    @staticmethod
    def _load(name):
        try:
            if name == 'python':
                import tree_sitter_python as m

                return ts.Language(m.language())
            if name == 'rust':
                import tree_sitter_rust as m

                return ts.Language(m.language())
            if name == 'javascript':
                import tree_sitter_javascript as m

                return ts.Language(m.language())
            import tree_sitter_typescript as m

            return ts.Language(m.language_tsx() if name == 'tsx' else m.language_typescript())
        except ImportError as e:
            raise ParserUnavailableError(name) from e
