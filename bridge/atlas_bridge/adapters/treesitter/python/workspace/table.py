"""The names one module defines at its top level: assignments, functions, classes and imports."""

import posixpath
from typing import NamedTuple

from ..syntax import PythonSyntax
from .modules import AbsoluteModule, RelativeModule


class Import(NamedTuple):
    """`import module` (attr None) or `from module import attr`."""

    module: object  # a ModuleRef
    attr: str | None


class ModuleTable:
    """Top-level names of one file, read once: assignments, functions, classes and imports."""

    def __init__(self, source):
        self._source = source
        self._assigns = {}  # name -> [(end byte, value node)], in source order
        self._functions = {}  # name -> function_definition
        self._classes = {}  # name -> class_definition
        self._imports = {}  # name -> Import
        self._stars = {}  # start byte of a `from module import *` statement -> its ModuleRef
        for st in PythonSyntax.module_statements(source.root):
            self._read(st)

    def assignments(self, name):
        """[(end byte, value node)] of the module-level assignments of a name, in source order."""
        return self._assigns.get(name, ())

    def function(self, name):
        return self._functions.get(name)

    def class_definition(self, name):
        return self._classes.get(name)

    def imported(self, name) -> Import | None:
        return self._imports.get(name)

    def star_import(self, statement):
        """The ModuleRef a module-level `from module import *` statement of this file imports, or None."""
        return self._stars.get(statement.start_byte)

    def _read(self, st):
        t = st.type
        if t == 'decorated_definition':
            st = st.child_by_field_name('definition')
            t = st.type if st is not None else ''
        if t == 'expression_statement':
            self._assignments(st)
        elif t == 'function_definition':
            self._functions[PythonSyntax.name(st)] = st
        elif t == 'class_definition':
            self._classes[PythonSyntax.name(st)] = st
        elif t == 'import_statement':
            self._import(st)
        elif t == 'import_from_statement':
            self._import_from(st)

    def _assignments(self, st):
        for a in st.named_children:
            if a.type == 'assignment':
                for n, v in PythonSyntax.assignment_targets(a):
                    self._assigns.setdefault(n, []).append((a.end_byte, v))

    def _import(self, st):
        text = PythonSyntax.text
        for n in st.named_children:
            if n.type == 'aliased_import':
                module = AbsoluteModule(text(n.child_by_field_name('name')))
                self._imports[text(n.child_by_field_name('alias'))] = Import(module, None)
            elif n.type == 'dotted_name':
                top = text(n).split('.')[0]
                self._imports[top] = Import(AbsoluteModule(top), None)

    def _import_from(self, st):
        text = PythonSyntax.text
        ref = self._module_ref(st.child_by_field_name('module_name'))
        if any(c.type == 'wildcard_import' for c in st.children):
            self._stars[st.start_byte] = ref
        for n in st.children_by_field_name('name'):
            if n.type == 'aliased_import':
                self._imports[text(n.child_by_field_name('alias'))] = Import(ref, text(n.child_by_field_name('name')))
            else:
                self._imports[text(n)] = Import(ref, text(n))

    def _module_ref(self, mod):
        text = PythonSyntax.text
        if mod is None or mod.type != 'relative_import':
            return AbsoluteModule(text(mod))
        prefix = next((c for c in mod.children if c.type == 'import_prefix'), None)
        dotted = next((c for c in mod.named_children if c.type == 'dotted_name'), None)
        base = posixpath.dirname(self._source.path)
        for _ in range(len(text(prefix)) - 1):
            base = posixpath.dirname(base)
        if dotted is not None:
            base = posixpath.join(base, *text(dotted).split('.'))
        return RelativeModule(base)
