"""The tasks a repository defines: functions a task library's decorator registers, and the name each is sent by."""

from typing import NamedTuple

from ..channels.arguments import ChannelArguments
from ..channels.types import LibraryTypes
from ..qualified import QualifiedNames
from ..scope import Scope
from ..syntax import PythonSyntax
from .modules import ModuleNames
from .table import TaskTable


class Task(NamedTuple):
    """A task definition: the function, the decorator line, and the name the workers know it by."""

    source: object
    function: object
    line: int
    name: str


class TaskDefinitions:
    """Every task definition of the repository, indexed by its function. A decorator whose `name=` cannot be read as
    one literal leaves the task out: its name is not known."""

    def __init__(self, workspace, values, origins, table=TaskTable):
        self._workspace = workspace
        self._table = table
        self._qualified = QualifiedNames(workspace)
        self._types = LibraryTypes(workspace, origins, table)
        self._arguments = ChannelArguments(workspace, values)
        self._modules = ModuleNames(s.path for s in workspace.sources)
        self._tasks = None  # (path, function start byte) -> Task, read on first use

    def all(self) -> list[Task]:
        return list(self._index().values())

    def named_by(self, source, node) -> Task | None:
        """The task a name or dotted expression refers to, through the file's imports, or None."""
        if node.type not in ('identifier', 'attribute') or self._local(source, node):
            return None
        found = self._workspace.names.expression(source, node)
        if found is None or not found.is_function:
            return None
        return self._index().get((found.source.path, found.node.start_byte))

    def is_app(self, node, scope) -> bool:
        """Whether an expression holds the library's app: an object one of its creators made, or the name the library
        exports for the current app."""
        qualified = self._qualified.of(scope.source, node)
        if any(QualifiedNames.matches(qualified, self._table.LIBRARY, a) for a in self._table.APPS):
            return True
        return any(made.type in self._table.TYPES for made in self._types.of(node, scope))

    def _local(self, source, node):
        """Whether the first name of an expression is a local or parameter of the function it is used in."""
        while node.type == 'attribute':
            node = node.child_by_field_name('object')
        func = PythonSyntax.ancestor(node, PythonSyntax.FUNCTION)
        if func is None or node.type != 'identifier':
            return False
        name = PythonSyntax.text(node)
        prior = self._workspace.locals.before(source, func, name, node.start_byte)
        return bool(prior) or name in PythonSyntax.param_names(func)

    def _index(self):
        if self._tasks is None:
            self._tasks = {}
            for source, decorated in self._workspace.decorated():
                task = self._task(source, decorated)
                if task is not None:
                    self._tasks[(source.path, task.function.start_byte)] = task
        return self._tasks

    def _task(self, source, decorated):
        function = decorated.child_by_field_name('definition')
        if function is None or function.type != 'function_definition' or self._workspace.is_test(source, function):
            return None
        scope = Scope.at(source, decorated)
        for decorator in (d for d in decorated.children if d.type == 'decorator' and d.named_children):
            expr = decorator.named_children[0]
            call = expr if expr.type == 'call' else None
            if not self._registers(call.child_by_field_name('function') if call else expr, scope):
                continue
            name = self._name(call, scope, source, function)
            return Task(source, function, PythonSyntax.line(decorator), name) if name else None
        return None

    def _registers(self, fn, scope):
        """Whether a decorator is one that makes a task: a function of the library, or a method of its app."""
        qualified = self._qualified.of(scope.source, fn)
        if any(QualifiedNames.matches(qualified, self._table.LIBRARY, f) for f in self._table.TASK_FUNCTIONS):
            return True
        if fn.type != 'attribute':
            return False
        method = PythonSyntax.text(fn.child_by_field_name('attribute'))
        return method in self._table.TASK_METHODS and self.is_app(fn.child_by_field_name('object'), scope)

    def _name(self, call, scope, source, function):
        """The name given with `name=`, else '<module>.<function>' for a function at module level, else ''."""
        nodes = ChannelArguments.nodes(self._table.NAME, call) if call is not None else []
        if nodes:
            texts = set(self._arguments.literals(nodes[0], scope))
            return texts.pop() if len(texts) == 1 else ''
        if PythonSyntax.ancestor(function, PythonSyntax.FUNCTION + PythonSyntax.CLASS) is not None:
            return ''  # a task defined inside a function or class: not named after its module alone
        return f'{self._modules.of(source.path)}.{PythonSyntax.name(function)}'
