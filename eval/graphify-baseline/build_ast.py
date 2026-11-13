"""Graphify's code-only (AST) graph of the current folder, secret-file filter off (as tools/demo/graphify_ast.py)."""

from pathlib import Path

import graphify.detect
from graphify.watch import _rebuild_code


def main():
    graphify.detect._is_sensitive = lambda path: False
    ok = _rebuild_code(Path('.'), force=True, acquire_lock=False)
    raise SystemExit(0 if ok else 1)


if __name__ == '__main__':
    main()
