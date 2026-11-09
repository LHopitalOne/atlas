"""The files of a repository as modules that export values to each other, read on demand while channels are read."""

import posixpath
import re

from ..syntax.nodes import JsSyntax
from .libraries import LibraryNames
from .values import ChannelValues


class ChannelFile:
    """One file as the channel readers see it: its JsModule, the libraries its names come from, its channel values,
    and what it exports to the files that import it."""

    DECLARATIONS = frozenset({'function_declaration', 'class_declaration'})
    EXPORTS = frozenset({'module.exports', 'exports'})

    def __init__(self, module, graph):
        self.module = module
        self.graph = graph
        self.libraries = LibraryNames(module)
        self.values = ChannelValues(module.scopes, self)

    @property
    def path(self):
        return self.module.path

    def imported(self, head):
        """(file, exported node) an identifier is imported from, when that file is in the repository."""
        found = self.libraries.source_of(head)
        if found is None:
            return None
        target = self.graph.file_for(self.path, found[0])
        if target is None:
            return None
        node = target.exported(found[1])
        return (target, node) if node is not None else None

    def exported(self, name):
        """The expression a file exports as `name` ('default' for `module.exports = x` / `export default x`): an
        exported or top-level declaration, a key of `module.exports = {...}`, or `exports.name = x`."""
        for child in self.module.source.root.named_children:
            found = self._export(child, name)
            if found is not None:
                return found
        return None

    def _export(self, child, name):
        if child.type == 'export_statement':
            value = child.child_by_field_name('value')
            if value is not None:
                return value if name == LibraryNames.DEFAULT else None
            child = child.child_by_field_name('declaration') or child
        if child.type in JsSyntax.DECLARATIONS:
            return self._declared(child, name)
        if child.type in self.DECLARATIONS:
            return child if JsSyntax.text(child.child_by_field_name('name')) == name else None
        if child.type == 'expression_statement' and child.named_children:
            return self._assigned(child.named_children[0], name)
        return None

    @staticmethod
    def _declared(declaration, name):
        for d in declaration.named_children:
            if d.type == 'variable_declarator' and JsSyntax.text(d.child_by_field_name('name')) == name:
                return d.child_by_field_name('value')
        return None

    def _assigned(self, expr, name):
        """`module.exports = x`, `module.exports = { name }`, `exports.name = x`."""
        if expr.type != 'assignment_expression':
            return None
        left, right = JsSyntax.text(expr.child_by_field_name('left')), expr.child_by_field_name('right')
        if left in self.EXPORTS:
            if name == LibraryNames.DEFAULT:
                return right
            return JsSyntax.prop(right, name)
        owner, _, key = left.rpartition('.')
        return right if owner in self.EXPORTS and key == name else None


class ModuleGraph:
    """The repository's files by path, each read into a ChannelFile the first time something needs it. Files read
    this way are released together (clear), so memory holds only what one file's channels reached."""

    SCRIPT = re.compile(r'\.(?:[mc]?js|jsx)$')  # typescript imports './config.js' for config.ts
    SUFFIXES = ('', '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '/index.ts', '/index.tsx', '/index.js')
    MAX_FILES = 64  # files one reading may open

    def __init__(self, workspace):
        self._workspace = workspace
        self._files = {}
        self._own = set()  # paths whose modules this graph made (and so releases)

    def adopt(self, module) -> ChannelFile:
        """The file of a module someone else made and releases."""
        if module.path not in self._files:
            self._files[module.path] = ChannelFile(module, self)
        return self._files[module.path]

    def file(self, path) -> ChannelFile | None:
        """The file at `path` (read on first use), or None when it is not in the workspace."""
        if path in self._files:
            return self._files[path]
        source = self._workspace.source(path)
        if source is None or len(self._own) >= self.MAX_FILES:
            return None
        self._own.add(path)
        return self.adopt(self._workspace.module(source))

    def file_for(self, importer, spec) -> ChannelFile | None:
        """The file a relative import of `importer` names (`./config.js` may be config.ts), or None."""
        path = self.path_for(importer, spec)
        return self.file(path) if path is not None else None

    def path_for(self, importer, spec) -> str | None:
        """The path of the workspace file a relative import names, without reading it."""
        if not spec.startswith('.'):
            return None
        base = posixpath.normpath(posixpath.join(posixpath.dirname(importer), spec))
        for stem in dict.fromkeys((base, self.SCRIPT.sub('', base))):
            for suffix in self.SUFFIXES:
                if self._workspace.source(stem + suffix) is not None:
                    return stem + suffix
        return None

    def importers(self, path, name):
        """The other files that mention `name` and import something from `path`."""
        needle = name.encode()
        for source in self._workspace.sources:
            if source.path == path or not source.mentions(needle) or not source.mentions(b'import', b'require'):
                continue
            found = self.file(source.path)
            if found is not None and self._imports(found, path):
                yield found

    def _imports(self, file, path):
        return any(self.path_for(file.path, spec) == path for spec in file.libraries.specs())

    def clear(self):
        """Release the modules this graph read and forget every file."""
        for path in self._own:
            self._files[path].module.release()
        self._files, self._own = {}, set()
