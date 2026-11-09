"""Monorepo: the workspace a repository folder sits in, and the packages it declares by name."""

import json
import os
import re

from .globs import FolderGlobs


class WorkspaceFiles:
    """The package folders a workspace root declares: `packages:` in pnpm-workspace.yaml, `workspaces` in
    package.json (a list, or `{ packages: [...] }`)."""

    PNPM = 'pnpm-workspace.yaml'
    PACKAGE = 'package.json'
    # the `packages:` key, with its list inline (`packages: ['a', 'b']`) or on the lines under it
    PACKAGES_KEY = re.compile(r'^packages\s*:\s*(?:\[(?P<inline>[^\]]*)\])?\s*(?:#.*)?$')
    ITEM = re.compile(r'^\s+-\s*[\'"]?(?P<glob>[^\'"#\s]+)[\'"]?')  # `  - 'packages/*'` under it
    TOP_KEY = re.compile(r'^\S')  # the next top-level key ends the list
    INLINE_ITEM = re.compile(r'[\'"]?(?P<glob>[^\'",\s]+)[\'"]?')  # an item of `packages: ['a', 'b']`

    @classmethod
    def patterns(cls, folder) -> list[str]:
        """The package globs the folder declares as a workspace root; [] when it is not one."""
        return cls._pnpm(folder) or cls._npm(folder)

    @classmethod
    def _pnpm(cls, folder):
        text = cls._read(os.path.join(folder, cls.PNPM))
        out, inside = [], False
        for line in text.splitlines():
            key = cls.PACKAGES_KEY.match(line)
            if key is not None:
                inside = key.group('inline') is None
                out += [m.group('glob') for m in cls.INLINE_ITEM.finditer(key.group('inline') or '')]
            elif inside and cls.TOP_KEY.match(line):
                inside = False
            elif inside and cls.ITEM.match(line):
                out.append(cls.ITEM.match(line).group('glob'))
        return out

    @classmethod
    def _npm(cls, folder):
        manifest = cls.manifest(folder)
        given = manifest.get('workspaces') if manifest else None
        if isinstance(given, dict):
            given = given.get('packages')
        return [g for g in given if isinstance(g, str)] if isinstance(given, list) else []

    @classmethod
    def manifest(cls, folder) -> dict:
        """The folder's package.json, or {} when it has none that can be read."""
        try:
            found = json.loads(cls._read(os.path.join(folder, cls.PACKAGE)) or '{}')
        except ValueError:
            return {}
        return found if isinstance(found, dict) else {}

    @staticmethod
    def _read(path):
        try:
            with open(path, encoding='utf-8') as f:
                return f.read()
        except (OSError, UnicodeDecodeError):
            return ''


class Monorepo:
    """The workspace around a repository folder: the nearest folder at or above it that declares workspace packages,
    looked for up to the folder that holds `.git` (else the git root itself, whose packages are the folders with a
    package.json a few levels down). Package names map to their folders."""

    MAX_LEVELS = 8  # folders looked at above the repository
    GIT = '.git'
    FALLBACK = ('*', '*/*', '*/*/*')  # where packages are looked for in a git root that declares no workspace

    def __init__(self, root, patterns):
        self._root = root
        self._patterns = tuple(patterns)
        self._packages = None

    @property
    def root(self) -> str:
        return self._root

    @classmethod
    def around(cls, folder) -> 'Monorepo | None':
        here = os.path.abspath(folder)
        for _ in range(cls.MAX_LEVELS):
            patterns = WorkspaceFiles.patterns(here)
            if patterns:
                return cls(here, patterns)
            if os.path.exists(os.path.join(here, cls.GIT)):
                return cls(here, cls.FALLBACK)
            parent = os.path.dirname(here)
            if parent == here:
                return None
            here = parent
        return None

    def packages(self) -> dict:
        """{package name: its folder}, the first folder of a name winning."""
        if self._packages is None:
            self._packages = {}
            for folder in FolderGlobs(self._root).expand(self._patterns):
                name = WorkspaceFiles.manifest(folder).get('name')
                if isinstance(name, str) and name:
                    self._packages.setdefault(name, folder)
        return self._packages
