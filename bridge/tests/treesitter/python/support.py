"""Shared helpers: run the Python extractor over a few files written to a temporary folder."""

import os
import tempfile
import textwrap

from atlas_bridge.adapters.treesitter.kit import Grammar, RepositoryFiles, SourceFile
from atlas_bridge.adapters.treesitter.python import PythonExtractor
from atlas_bridge.adapters.treesitter.python.policy import PythonTestPolicy
from atlas_bridge.adapters.treesitter.python.syntax import PythonSyntax
from atlas_bridge.adapters.treesitter.python.workspace import PythonWorkspace


def extract(files, repo='svc', graph=None):
    """The extraction of `files` ({path: source}); a missing file in the list is skipped, not an error. `graph`: a
    CallGraph standing in for SCIP indexes."""
    with tempfile.TemporaryDirectory() as d:
        for path, src in files.items():
            full = os.path.join(d, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, 'w', encoding='utf-8') as f:
                f.write(textwrap.dedent(src))
        return PythonExtractor(graph).extract(repo, RepositoryFiles(d), sorted(files) + ['missing.py'])


def routes(ex):
    return {(str(r.path), tuple(sorted(r.methods))) for r in ex.routes}


def requests_(ex, test=False):
    return {(c.method, str(c.path)) for c in ex.calls if c.kind == 'request' and c.test == test}


def call(ex, path):
    return next(c for c in ex.calls if str(c.path) == path)


def workspace(files):
    """A PythonWorkspace over in-memory files ({path: source})."""
    policy, grammar = PythonTestPolicy(), Grammar.named('python')
    sources = [SourceFile(p, src.encode(), grammar, policy.is_test(p)) for p, src in sorted(files.items())]
    return PythonWorkspace('svc', sources)


def node(source, kind, text):
    """The first node of a type whose text is `text`."""
    return next(n for n in PythonSyntax.walk(source.root, (kind,)) if PythonSyntax.text(n) == text)
