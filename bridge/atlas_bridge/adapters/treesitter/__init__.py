"""Adapter: finds HTTP routes and requests in source code with tree-sitter. Implements usecases.link.Extractor.

Each language module exposes `extract(repo, root, paths) -> Extraction` over every file of that language at once,
because routes and request helpers are often resolved across files (Django includes, wrapper functions).
"""

import os

from ...core.http import Extraction
from . import javascript, python, rust
from .common import EXTENSIONS, list_files

MODULES = {'python': python, 'rust': rust, 'javascript': javascript, 'typescript': javascript, 'tsx': javascript}


class TreeSitterExtractor:
    def extract(self, repo: str, root: str) -> Extraction:
        by_module = {}
        for p in list_files(root):
            mod = MODULES[EXTENSIONS[os.path.splitext(p)[1]]]
            by_module.setdefault(mod, []).append(p)
        out = Extraction()
        for mod, paths in by_module.items():
            out.extend(mod.extract(repo, root, paths))
        return out
