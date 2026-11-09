"""Adapter: finds HTTP routes and requests in source code with tree-sitter (implements usecases.ports.Extractor).

kit/ holds the base classes every language builds on; each language package has a workspace (repo-wide indexes),
a value resolver, one collector per framework or request idiom, and an extractor that wires them together.
"""

from .extractor import TreeSitterExtractor
from .kit import FileMentions

__all__ = ['FileMentions', 'TreeSitterExtractor']
