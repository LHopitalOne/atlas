"""WorkspacePackage: a package of the monorepo, read from its source like a small repository of its own."""

import posixpath

from .....core.errors import SourceReadError
from ...kit import Grammar, RepositoryFiles, SourceFile
from ..syntax.nodes import JsSyntax
from .monorepo import WorkspaceFiles


class PackageEntry:
    """The source file a package import names: the file package.json points at (`source`, `exports`, `module`,
    `main`, `types`), read from its source folder when it points at build output (`build/index.js` ->
    `src/index.ts`), else an index file."""

    FIELDS = ('source', 'exports', 'module', 'main', 'types', 'typings')
    BUILT = ('build', 'dist', 'lib', 'out', 'esm', 'cjs')  # folders compiled code is written to
    SOURCE = 'src'
    COMPILED = ('.d.ts', '.d.mts', '.js', '.mjs', '.cjs')  # extensions of compiled files
    CONDITIONS = ('source', 'import', 'default', 'require', 'types')  # in a conditional `exports` entry, in order
    INDEX = ('./src/index', './index')

    @classmethod
    def candidates(cls, manifest, subpath='') -> list[str]:
        """Relative imports ('./src/index') the package entry may be, most likely first."""
        if subpath:
            return [f'./{subpath}', f'./{cls.SOURCE}/{subpath}']
        out = []
        for field in cls.FIELDS:
            target = cls._target(manifest.get(field))
            if target:
                out += [cls._source_of(target), target]
        return out + list(cls.INDEX)

    @classmethod
    def _target(cls, given):
        """The path a package.json field gives: a string, or the '.' entry of an exports map and its conditions."""
        for _ in range(4):
            if isinstance(given, dict):
                given = given.get('.', next((given[c] for c in cls.CONDITIONS if c in given), None))
            elif isinstance(given, list):
                given = given[0] if given else None
        return given if isinstance(given, str) else ''

    @classmethod
    def _source_of(cls, target):
        """'./build/index.js' -> './src/index': where the compiled file's source is usually kept."""
        parts = posixpath.normpath(target).split('/')
        if parts and parts[0] in cls.BUILT:
            parts[0] = cls.SOURCE
        path = '/'.join(parts)
        for ext in cls.COMPILED:
            if path.endswith(ext):
                return './' + path.removesuffix(ext)
        return './' + path


class WorkspacePackage:
    """The source files of one package folder (at most MAX_FILES), and where the names it exports are defined."""

    MAX_FILES = 3000
    MAX_DEPTH = 8  # re-exports followed
    IMPORTER = 'package.json'  # entry imports are read as if written next to package.json

    def __init__(self, name, folder, factory):
        self._name = name
        self._folder = folder
        self._manifest = WorkspaceFiles.manifest(folder)
        self._workspace = factory(name, self._read(folder), folder)  # a JavaScriptWorkspace of the package
        self._linker = self._workspace.linker()

    @property
    def workspace(self):
        return self._workspace

    @property
    def linker(self):
        return self._linker

    def definition(self, subpath, name):
        """(module, the expression or declaration exported as `name`, the name it is defined under) where the entry
        of an import of the package (`subpath` after its name) leads, following `export * from` and
        `export { name } from`; None if not found."""
        for candidate in PackageEntry.candidates(self._manifest, subpath):
            module = self._linker.module(self.IMPORTER, candidate)
            if module is not None:
                return self._defined(module, name, 0)
        return None

    def _defined(self, module, name, depth):
        value = module.exports.value(name)
        if value is not None:
            return module, value, name
        if depth >= self.MAX_DEPTH:
            return None
        for statement in module.source.root.named_children:
            source = statement.child_by_field_name('source') if statement.type == 'export_statement' else None
            wanted = self._reexported(statement, name) if source is not None else None
            target = self._linker.module(module.path, JsSyntax.string(source)) if wanted else None
            found = self._defined(target, wanted, depth + 1) if target is not None else None
            if found is not None:
                return found
        return None

    @staticmethod
    def _reexported(statement, name):
        """The name another module exports `name` under, when this re-export passes it on; None otherwise."""
        clauses = [c for c in statement.named_children if c.type == 'export_clause']
        if not clauses:
            spaced = any(c.type == 'namespace_export' for c in statement.named_children)
            return None if spaced else name  # `export * from './x'` passes on every name
        for spec in clauses[0].named_children:
            local, alias = spec.child_by_field_name('name'), spec.child_by_field_name('alias')
            if local is not None and JsSyntax.text(alias or local) == name:
                return JsSyntax.text(local)
        return None

    @classmethod
    def _read(cls, folder):
        files = RepositoryFiles(folder)
        out = []
        for path in files.paths()[: cls.MAX_FILES]:
            if Grammar.BY_EXTENSION.get(path[path.rfind('.') :]) not in ('javascript', 'typescript', 'tsx'):
                continue
            try:
                out.append(SourceFile(path, files.read(path), Grammar.for_path(path), False))
            except SourceReadError:
                continue
        return out

    def release(self):
        self._linker.release()
