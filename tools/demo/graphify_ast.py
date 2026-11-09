"""Graphify's code-only (AST) graph of the current folder, with Graphify's secret-file filter turned off.

Graphify skips any path with a segment like "credentials", which drops Open edX's whole `credentials` repository.
Run this only on a folder that holds source files you chose (tools/demo/build.sh mirrors each repository's
production code into one first). Usage: cd <mirror> && python graphify_ast.py
"""

from pathlib import Path

import graphify.detect
from graphify.watch import _rebuild_code


def main():
    graphify.detect._is_sensitive = lambda path: False
    ok = _rebuild_code(Path('.'), force=True, acquire_lock=False)
    raise SystemExit(0 if ok else 1)


if __name__ == '__main__':  # Graphify extracts in worker processes, which import this file again
    main()
