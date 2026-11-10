"""ModuleLinker: the files of the repository that relative imports name, read on demand for the values they export."""

import posixpath
import re

from .source import JsSource


class ModuleLinker:
    """Opens the file an import names (`import { config } from '../config'`) as a module of its own, so a value can
    be followed into it. Each file is read once per linker, with a tree of its own (the pass may release the file's
    shared tree at any time), and at most MAX_MODULES files are held; a pass makes a new linker."""

    MAX_MODULES = 256
    MODULE_EXTS = ('', '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs')  # how an import names a file
    SCRIPT_EXTS = ('.js', '.mjs', '.cjs', '.jsx')  # extensions an import may spell out for a typescript file
    INDEX = 'index'
    # a path alias, not a package: '@/lib/api', '~/utils', '$lib/constants' (SvelteKit), '#app/x', 'src/x' (baseUrl);
    # '@scope/name' is a package
    ALIAS = re.compile(r'^(?:@|~~?|[#$][\w-]*|src)/(?P<rest>.+)$')

    def __init__(self, sources, factory):
        self._by_path = {s.path: s for s in sources}
        self._factory = factory  # JsSource, linker -> JsModule
        self._modules = {}
        self._aliased = {}  # alias import -> the only file it can name, or None

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
        """The repository path a relative import names, or the only file a path alias can name; else None."""
        if not source.startswith('.'):
            return self._alias(source)
        return self._file(posixpath.normpath(posixpath.join(posixpath.dirname(importer), source)))

    def _alias(self, source):
        """`$lib/constants` -> 'src/lib/constants.ts' when that is the one file whose path ends in 'lib/constants' or
        'constants' after a folder (the alias's folder is configured where this does not look: svelte.config.js,
        vite.config.ts, a generated tsconfig). Two files that fit leave it unknown."""
        m = self.ALIAS.match(source)
        if m is None:
            return None
        if source not in self._aliased:
            rest = m.group('rest')
            fits = {p for p in self._by_path if self._ends_in(p, rest)}
            self._aliased[source] = fits.pop() if len(fits) == 1 else None
        return self._aliased[source]

    def _ends_in(self, path, rest):
        stem = posixpath.splitext(path)[0] if path.endswith(self.MODULE_EXTS[1:]) else path
        stem = stem.removesuffix('/' + self.INDEX) if not rest.endswith(self.INDEX) else stem
        return stem == rest or stem.endswith('/' + rest)

    def _file(self, base):
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
