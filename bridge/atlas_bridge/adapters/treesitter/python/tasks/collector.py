"""TaskEndpoints: the tasks a repository defines, as routes, and the calls that hand them to workers, as calls."""

import dataclasses

from .....core.http import Extraction, Protocol
from ...kit import CallCollector, RouteCollector
from ..channels.arguments import ChannelArguments
from ..channels.values import ChannelValues
from ..qualified import QualifiedNames
from ..scope import Scope
from ..syntax import PythonSyntax
from .definitions import TaskDefinitions
from .table import TaskTable


class TaskEndpoints(RouteCollector, CallCollector):
    """A task definition receives on '/<task name>'. A call sends there when it is a sending method of a name that
    resolves, through the file's imports, to exactly one task definition (`send_mail.delay(...)`), or when it names
    the task as a literal (`app.send_task('proj.tasks.send_mail')`). Anything else is left out, never guessed."""

    framework = TaskTable.LIBRARY

    def __init__(self, workspace, table=TaskTable):
        super().__init__(workspace)
        values = ChannelValues(workspace)
        self._table = table
        self._tasks = TaskDefinitions(workspace, values, values.origins, table)
        self._arguments = ChannelArguments(workspace, values)
        self._qualified = QualifiedNames(workspace)
        callees = ' '.join(f'"{n}"' for n in sorted(table.callees()))
        self._query = f"""
        (call function: [(identifier) @fn (attribute attribute: (identifier) @fn)] (#any-of? @fn {callees})) @call
        """

    def collect(self) -> Extraction:
        out = Extraction()
        for task in self._tasks.all():
            route = self.route(task.source, task.line, '/' + task.name, handler=PythonSyntax.name(task.function))
            out.routes.append(dataclasses.replace(route, protocol=Protocol.TASK))
        for source in self.workspace.sources:
            for call in source.captures(self._query).get('call', ()):
                scope = Scope.at(source, call)
                for name in self._sent(call, scope):
                    out.calls.append(self._call(name, call, scope))
        return out

    def _call(self, name, call, scope):
        test = self.workspace.is_test(scope.source, call)
        line = PythonSyntax.line(call)
        return self.call(scope.source, line, '/' + name, function=scope.qualified, test=test, protocol=Protocol.TASK)

    def _sent(self, call, scope) -> list[str]:
        """The names of the tasks a call sends: one for a task's own method, the literals of a by-name send."""
        fn = call.child_by_field_name('function')
        callee = PythonSyntax.callee(call)
        receiver = fn.child_by_field_name('object') if fn.type == 'attribute' else None
        if receiver is not None and callee in self._table.SENDS:
            task = self._tasks.named_by(scope.source, receiver)
            if task is not None:
                return [task.name]
        for by_name in self._table.BY_NAME:
            if self._by_name(by_name, fn, callee, receiver, scope):
                nodes = ChannelArguments.nodes(by_name.name, call)
                texts = self._arguments.literals(nodes[0], scope) if nodes else []
                return [t for t in dict.fromkeys(texts) if ChannelArguments.NAME.match(t)]
        return []

    def _by_name(self, by_name, fn, callee, receiver, scope):
        if receiver is not None and callee == by_name.method and self._tasks.is_app(receiver, scope):
            return True
        if not by_name.function or callee != by_name.function:
            return False
        return QualifiedNames.matches(self._qualified.of(scope.source, fn), self._table.LIBRARY, by_name.function)
