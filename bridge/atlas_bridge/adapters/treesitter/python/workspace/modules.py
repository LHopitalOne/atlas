"""Python modules: references to them (absolute or relative imports) and the files they live in."""

from abc import ABC, abstractmethod


class ModuleRef(ABC):
    """A module an import names, found in the repository by ModuleIndex.locate()."""

    SEPARATOR = '.'

    __slots__ = ('name',)

    def __init__(self, name: str):
        self.name = name

    def child(self, attr: str) -> 'ModuleRef':
        """The submodule `attr` of this module (package.attr)."""
        return type(self)(self.name + self.SEPARATOR + attr)

    @abstractmethod
    def locate(self, modules: 'ModuleIndex'):
        """The SourceFile of this module, or None when it is not in the repository."""


class AbsoluteModule(ModuleRef):
    """`import a.b` or `from a.b import c`: a dotted name, matched against any suffix of a file's module path."""

    def locate(self, modules):
        return modules.dotted(self.name)


class RelativeModule(ModuleRef):
    """`from ..a import b`: a folder path relative to the repository root."""

    SEPARATOR = '/'

    def locate(self, modules):
        return modules.at(self.name)


class ModuleIndex:
    """Every dotted module name a file may be imported by: 'src/app/utils/snuba.py' is 'snuba', 'utils.snuba', ...

    When several files answer to a name, production code wins over tests (by `policy`, a TestPathPolicy), then the
    shortest path.
    """

    def __init__(self, sources, policy):
        self._files = {s.path: s for s in sources}
        self._by_name = {}
        for path in self._files:
            parts = path.removesuffix('.py').split('/')
            if parts[-1] == '__init__':
                parts = parts[:-1]
            for k in range(len(parts)):
                self._by_name.setdefault('.'.join(parts[k:]), []).append(path)
        for paths in self._by_name.values():
            paths.sort(key=lambda p: (policy.is_test(p), len(p)))

    def dotted(self, name: str):
        paths = self._by_name.get(name)
        return self._files[paths[0]] if paths else None

    def at(self, base: str):
        """The module at a folder path: base.py, else base/__init__.py."""
        return self._files.get(base + '.py') or self._files.get(base + '/__init__.py')
