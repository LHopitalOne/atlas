"""WorkspacePackageCalls: requests sent by functions an application imports from a package of its monorepo."""

import os

from .....core.http import Extraction
from ...kit import CallCollector
from ..bindings.imports import ImportTable
from .exported import PackageFunctions
from .forwarder import PackageForwarder, PassedFunctions
from .monorepo import Monorepo
from .package import WorkspacePackage


class PackageImports:
    """{import specifier: {imported names}} for the imports of the repository's files that name a package of the
    monorepo (`@acme/sdk`, or `@acme/sdk/sub` for a subpath), with the package each specifier names."""

    def __init__(self, workspace, packages):
        self.names, self.packages = {}, {}
        needles = tuple(name.encode() for name in packages)
        for source in workspace.sources:
            if source.test or not source.mentions(*needles):
                continue
            for specifier, imported in ImportTable(source).names().values():
                package = self._package(specifier, packages)
                if package is not None and imported != ImportTable.DEFAULT:
                    self.names.setdefault(specifier, set()).add(imported)
                    self.packages[specifier] = package
            source.release()

    @staticmethod
    def _package(specifier, packages):
        """(package name, subpath) the specifier imports, or None for a module of no package of the monorepo."""
        for name in packages:
            if specifier == name or specifier.startswith(name + '/'):
                return name, specifier[len(name) :].lstrip('/')
        return None


class WorkspacePackageCalls(CallCollector):
    """A function imported from a package of the same monorepo (a folder whose package.json `name` the import
    names, found from the workspace root: pnpm-workspace.yaml, package.json `workspaces`) is followed into the
    package's source as if it were in the repository: each request it sends is reported where the application
    calls it (`getPerson({ id })`), its path filled in with the call's arguments, or where the application hands the
    function on as a value (`asMutation(deleteSession)`), its parameters left as parameters. Only the files where the
    imported names are defined are read, and only inside the monorepo; the repository's own package is not."""

    def collect(self) -> Extraction:
        root = self.workspace.root
        monorepo = Monorepo.around(root) if root else None
        if monorepo is None:
            return Extraction()
        packages = {n: f for n, f in monorepo.packages().items() if not self._holds(f, root)}
        imports = PackageImports(self.workspace, packages) if packages else None
        if imports is None or not imports.names:
            return Extraction()
        opens = self._opens(imports, packages)
        pending = PackageForwarder(self.workspace, imports.names).settle(opens)
        pending += PassedFunctions(self.workspace, opens).requests()
        return Extraction(
            calls=[self.call(p.source, p.line, p.path, p.method, p.function, p.hints, test=p.test) for p in pending]
        )

    def _opens(self, imports, packages):
        read, out = {}, []
        factory = type(self.workspace)
        for specifier, names in sorted(imports.names.items()):
            name, subpath = imports.packages[specifier]
            if name not in read:
                package = WorkspacePackage(name, packages[name], lambda n, s, f: factory(n, s, root=f))
                read[name] = (package, PackageFunctions(package))
            out += read[name][1].opens(specifier, subpath, names)
        for package, _ in read.values():
            package.release()
        return out

    @staticmethod
    def _holds(folder, root):
        """The package folder is the repository's own folder or one around it (its own package)."""
        folder, root = os.path.abspath(folder), os.path.abspath(root)
        return root == folder or root.startswith(folder.rstrip(os.sep) + os.sep)
