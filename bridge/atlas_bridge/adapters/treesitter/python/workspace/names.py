"""What a module-level name means in a file, followed through imports into other modules."""

from dataclasses import dataclass

from ..syntax import PythonSyntax
from .modules import AbsoluteModule
from .table import ModuleTable


@dataclass(frozen=True, slots=True, eq=False)
class Symbol:
    """What a name refers to: a value (its assigned expression), a function, a class, or a module."""

    VALUE, FUNCTION, CLASS, MODULE = 'value', 'def', 'class', 'module'

    kind: str
    source: object = None  # the file that defines it
    node: object = None  # the assigned expression, or the function or class definition
    ref: object = None  # for a module: its ModuleRef

    @property
    def is_value(self):
        return self.kind == self.VALUE

    @property
    def is_module(self):
        return self.kind == self.MODULE

    @property
    def is_function(self):
        return self.kind == self.FUNCTION

    @property
    def is_class(self):
        return self.kind == self.CLASS


class NameLookup:
    """Resolves module-level names and dotted expressions to Symbols, following at most MAX_IMPORTS imports."""

    MAX_IMPORTS = 5

    def __init__(self, modules):
        self._modules = modules  # ModuleIndex
        self._tables = {}  # path -> ModuleTable, read on first use

    def table(self, source) -> ModuleTable:
        found = self._tables.get(source.path)
        if found is None:
            found = self._tables[source.path] = ModuleTable(source)
        return found

    def locate(self, ref):
        """The file of a ModuleRef, or None."""
        return ref.locate(self._modules)

    def dotted_module(self, dotted: str):
        """The file of a dotted module name ('proj.urls'), or None."""
        return self.locate(AbsoluteModule(dotted))

    def imported_from(self, source, name):
        """(file, attribute) when `name` comes from `from module import attribute` and the module is in the
        repository; else None."""
        imp = self.table(source).imported(name)
        if imp is None or imp.attr is None:
            return None
        module_file = self.locate(imp.module)
        return (module_file, imp.attr) if module_file is not None else None

    def lookup(self, source, name, depth=0, before=None):
        """What a module-level name means in a file, or None.

        A value is the name's last assignment, or with `before` (a use at module level, which runs in order) the
        last one that ends before that byte, so `BASE = BASE + '/api'` reads the previous BASE.
        """
        if depth > self.MAX_IMPORTS:
            return None
        table = self.table(source)
        value = self._assigned(table.assignments(name), before)
        if value is not None:
            return Symbol(Symbol.VALUE, source, value)
        function = table.function(name)
        if function is not None:
            return Symbol(Symbol.FUNCTION, source, function)
        klass = table.class_definition(name)
        if klass is not None:
            return Symbol(Symbol.CLASS, source, klass)
        return self._imported(table.imported(name), depth)

    def _imported(self, imp, depth):
        if imp is None:
            return None
        if imp.attr is None:
            return Symbol(Symbol.MODULE, ref=imp.module)
        return self.member(imp.module, imp.attr, depth + 1)

    @staticmethod
    def _assigned(assigned, before):
        values = [v for end, v in assigned if before is None or end <= before]
        if not values and before is not None:  # used above its assignment: take a later one, never its own
            values = [v for end, v in assigned if not v.start_byte <= before < end]
        return values[-1] if values else None

    def member(self, ref, attr, depth):
        """`attr` of a module: a name it defines, else its submodule."""
        module_file = self.locate(ref)
        if module_file is not None:
            found = self.lookup(module_file, attr, depth)
            if found:
                return found
        sub = ref.child(attr)
        return Symbol(Symbol.MODULE, ref=sub) if self.locate(sub) is not None else None

    def expression(self, source, node, depth=0):
        """What a name or a dotted `module.attr` expression means, or None."""
        if node.type == 'identifier':
            return self.lookup(source, PythonSyntax.text(node), depth)
        if node.type == 'attribute' and depth <= self.MAX_IMPORTS:
            base = self.expression(source, node.child_by_field_name('object'), depth + 1)
            if base and base.is_module:
                attr = PythonSyntax.text(node.child_by_field_name('attribute'))
                return self.member(base.ref, attr, depth + 1)
        return None

    def value(self, source, node):
        """The Symbol of a name or dotted expression when it is a value, else None."""
        found = self.expression(source, node)
        return found if found and found.is_value else None
