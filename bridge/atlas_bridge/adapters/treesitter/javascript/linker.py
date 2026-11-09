"""ModuleLinker: the files of the repository that relative imports name, read on demand for the values they export."""

import posixpath

from .source import JsSource


class ModuleLinker:
    """Opens the file an import names (`import { config } from '../config'`) as a module of its own, so a value can
    be followed into it. Each file is read once per linker, with a tree of its own (the pass may release the file's
    shared tree at any time), and at most MAX_MODULES files are held; a pass makes a new linker."""

    MAX_MODULES = 256
    MODULE_EXTS = ('', '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs')  # how an import names a file
    SCRIPT_EXTS = ('.js', '.mjs', '.cjs', '.jsx')  # extensions an import may spell out for a typescript file
    INDEX = 'index'

    def __init__(self, sources, factory):
        self._by_path = {s.path: s for s in sources}
        self._factory = factory  # JsSource, linker -> JsModule
        self._modules = {}

    def module(self, importer: str, source: str):
        """The module a relative import of the file `importer` names, or None (a package, or a file not read)."""
        path = self.path(importer, source)
        if path is None:
            return None
        if path not in self._modules:
            if len(self._modules) >= self.MAX_MODULES:
                return None
            found = self._by_path[path]
            self._modules[path] = self._factory(JsSource(found.path, found.data, found.grammar, found.test), self)
        return self._modules[path]

    def path(self, importer: str, source: str):
        """The repository path a relative import names, or None."""
        if not source.startswith('.'):
            return None
        base = posixpath.normpath(posixpath.join(posixpath.dirname(importer), source))
        stems = [base, base + '/' + self.INDEX]
        stems += [base.removesuffix(ext) for ext in self.SCRIPT_EXTS if base.endswith(ext)]
        for stem in stems:
            for ext in self.MODULE_EXTS:
                if stem + ext in self._by_path:
                    return stem + ext
        return None

    @classmethod
    def may_name(cls, importer: str, source: str, path: str) -> bool:
        """An import of the file `importer` may name the repository file `path`: a relative import that leads to it,
        or a path alias or workspace package (`@/lib/api`) that ends in its name. A package import (`undici`) whose
        last word is another name does not."""
        stem = cls._stem(path)
        if source.startswith('.'):
            target = cls._stem(posixpath.normpath(posixpath.join(posixpath.dirname(importer), source)))
            return target in (stem, stem.removesuffix('/index'))
        last, name = posixpath.basename(cls._stem(source)), posixpath.basename(stem)
        return last == name or (name == cls.INDEX and last == posixpath.basename(posixpath.dirname(stem)))

    @classmethod
    def _stem(cls, path):
        for ext in cls.MODULE_EXTS[1:]:
            if path.endswith(ext):
                return path.removesuffix(ext)
        return path

    def release(self):
        """Drop every module read so far."""
        for module in self._modules.values():
            module.release()
        self._modules = {}
