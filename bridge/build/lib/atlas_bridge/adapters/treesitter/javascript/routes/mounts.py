"""Prefixes across files: `app.use('/prefix', router)` puts every route of `router` under '/prefix'."""

import os

from ..declarations.records import RouteDeclaration
from ..syntax.nodes import JsSyntax
from .files import FileRoutes


class MountGraph:
    """Which routers are mounted where, across the files that declare routes or mounts. A router is a
    (file path, receiver name) pair; receiver '*' stands for every router of a file (its default export unknown)."""

    EVERY = '*'
    MAX_DEPTH = 5  # mounts followed outwards from a router
    MODULE_EXTS = ('', '.js', '.ts', '.tsx', '.jsx', '.mjs', '.cjs')  # how an import names a file
    SCRIPT_EXTS = ('.js', '.mjs', '.cjs')  # extensions an import may spell out

    def __init__(self, files: list[FileRoutes]):
        self._by_path = {f.path: f for f in files}
        self._parents = {}  # router -> [(parent router, prefix)]
        for f in files:
            for mount in f.mounts:
                target = self._target(f, mount.child)
                if target is not None:
                    self._parents.setdefault(target, []).append(((f.path, mount.parent), mount.prefix))

    def prefixes(self, file: FileRoutes, route: RouteDeclaration):
        """Every prefix the route is mounted under, sorted ('' when it is not mounted)."""
        key = (file.path, route.receiver)
        return sorted(set(self._prefixes(key, {key})))

    def _prefixes(self, key, seen):
        found = self._parents.get(key, []) + self._parents.get((key[0], self.EVERY), [])
        found = [(parent, prefix) for parent, prefix in found if parent not in seen]  # a router mounted in itself
        if not found or len(seen) > self.MAX_DEPTH:
            return ['']
        return [p + prefix for parent, prefix in found for p in self._prefixes(parent, seen | {parent})]

    def _target(self, f: FileRoutes, child):
        """The router a mounted expression stands for."""
        if child.type == 'identifier':
            name = JsSyntax.text(child)
            imported = f.module.imports.get(name)
            if imported is None:
                return (f.path, name)
            source, member = imported
        else:
            source, member = JsSyntax.require(child), f.module.imports.DEFAULT
            if not source:
                return None
        target = self._resolve(f.path, source)
        if target is None:
            return None
        if member != f.module.imports.DEFAULT:
            return (target.path, member)
        return (target.path, target.module.imports.default_export() or self.EVERY)

    def _resolve(self, path, source):
        """The file a relative import names, among the files with routes or mounts."""
        if not source.startswith('.'):
            return None
        base = os.path.normpath(os.path.join(os.path.dirname(path), source)).replace(os.sep, '/')
        base = self._without_script_ext(base)
        for stem in (base, base + '/index'):
            for ext in self.MODULE_EXTS:
                if stem + ext in self._by_path:
                    return self._by_path[stem + ext]
        return None

    @classmethod
    def _without_script_ext(cls, base):
        for ext in cls.SCRIPT_EXTS:
            if base.endswith(ext):
                return base.removesuffix(ext)
        return base
