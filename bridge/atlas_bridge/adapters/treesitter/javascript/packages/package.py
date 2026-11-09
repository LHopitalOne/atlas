"""WorkspacePackage: a package of the monorepo, read from its source like a small repository of its own."""

import json
import os
import posixpath
import re

from .....core.errors import SourceReadError
from ...kit import Grammar, RepositoryFiles, SourceFile
from ..syntax.nodes import JsSyntax
from .monorepo import WorkspaceFiles


class CompilerFolders:
    """Where a package's TypeScript compiler writes its output and reads its source: `outDir` and `rootDir` of the
    `compilerOptions` in its tsconfig.json (JSON with comments and trailing commas)."""

    FILE = 'tsconfig.json'
    # a string (kept), or a comment (dropped)
    COMMENT = re.compile(r'(?P<string>"(?:\\.|[^"\\])*")|//[^\n]*|/\*.*?\*/', re.S)
    TRAILING_COMMA = re.compile(r',(?P<close>\s*[}\]])')

    @classmethod
    def of(cls, folder) -> tuple[str, str] | None:
        """(outDir, rootDir) as normalized relative folders ('build', 'src'), or None when the tsconfig does not
        give both (without rootDir the compiler takes the common folder of its inputs, which is not read here)."""
        options = cls._read(folder).get('compilerOptions')
        options = options if isinstance(options, dict) else {}
        out, root = options.get('outDir'), options.get('rootDir')
        if not isinstance(out, str) or not isinstance(root, str):
            return None
        return posixpath.normpath(out), posixpath.normpath(root)

    @classmethod
    def _read(cls, folder):
        try:
            with open(os.path.join(folder, cls.FILE), encoding='utf-8') as f:
                text = f.read()
        except (OSError, UnicodeDecodeError):
            return {}
        text = cls.COMMENT.sub(lambda m: m.group('string') or '', text)
        try:
            found = json.loads(cls.TRAILING_COMMA.sub(lambda m: m.group('close'), text))
        except ValueError:
            return {}
        return found if isinstance(found, dict) else {}


class PackageEntry:
    """The source file a package import names: the file package.json points at (`source`, `exports` and its subpath
    entries, `module`, `main`, `types`), read from the source folder of the package's tsconfig when it points at
    the compiler's output (`outDir: 'build'`, `rootDir: 'src'`: `build/index.js` -> `src/index.ts`). Without a
    tsconfig that says so, the common output folders (`dist/`, `build/`, ...) are tried against `src/`, and then an
    index file; each candidate is used only when the file exists."""

    FIELDS = ('source', 'exports', 'module', 'main', 'types', 'typings')
    BUILT = ('build', 'dist', 'lib', 'out', 'esm', 'cjs')  # folders compiled code is commonly written to
    SOURCE = 'src'
    COMPILED = ('.d.ts', '.d.mts', '.d.cts', '.js', '.mjs', '.cjs')  # extensions of compiled files
    CONDITIONS = ('source', 'import', 'default', 'require', 'types')  # in a conditional `exports` entry, in order
    INDEX = ('./src/index', './index')
    EXPORTS = 'exports'

    @classmethod
    def candidates(cls, manifest, subpath='', compiled=None) -> list[str]:
        """Relative imports ('./src/index') the package entry may be, most likely first. `compiled` is the
        (outDir, rootDir) of the package's tsconfig, or None."""
        if subpath:
            exports = manifest.get(cls.EXPORTS)
            given = exports.get(f'./{subpath}') if isinstance(exports, dict) else None
            target = cls._target(given) if given is not None else ''
            mapped = [cls._source_of(target, compiled), target] if target else []
            return mapped + [f'./{subpath}', f'./{cls.SOURCE}/{subpath}']
        out = []
        for field in cls.FIELDS:
            target = cls._target(manifest.get(field))
            if target:
                out += [cls._source_of(target, compiled), target]
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
    def _source_of(cls, target, compiled=None):
        """'./build/index.js' -> './src/index': the source the compiled file is made from."""
        path = posixpath.normpath(target)
        out_dir, root_dir = compiled if compiled is not None else ('', '')
        if out_dir and out_dir != '.' and (path + '/').startswith(out_dir + '/'):
            path = posixpath.normpath(posixpath.join(root_dir, path[len(out_dir) :].lstrip('/')))
        elif compiled is None and path.split('/')[0] in cls.BUILT:
            path = posixpath.join(cls.SOURCE, path.split('/', 1)[1] if '/' in path else '')
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
        self._compiled = CompilerFolders.of(folder)
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
        for candidate in PackageEntry.candidates(self._manifest, subpath, self._compiled):
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
