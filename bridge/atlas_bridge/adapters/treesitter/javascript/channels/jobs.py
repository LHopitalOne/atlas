"""The jobs of a task queue (bullmq): the names a call adds jobs by, and those a worker's processor dispatches on."""

from ..syntax.functions import Functions
from ..syntax.nodes import JsSyntax
from ..values.urls import UrlText


class JobReadings:
    """Reads job names in one file (a ChannelFile). A worker takes the jobs its processor tells apart with
    `switch (job.name)`: one channel per case. A processor that dispatches on nothing (or on a case whose name is not
    known) takes every job of its queue, EVERY."""

    NAME = 'name'  # the property of a job (and of an added job's options object) that names it
    PROCESS = 'process'  # the method of a worker class that runs its jobs (WorkerHost.process)
    EVERY = '/{job}'
    MAX_DEPTH = 3  # bindings followed to a processor function

    def __init__(self, file):
        self._file = file

    @staticmethod
    def names(file, node, hints) -> list[str]:
        """'/<name>' for each literal job or queue name an expression holds."""
        out = []
        for value in file.values.candidates(node, hints):
            if value and not UrlText.PLACEHOLDER.search(value) and not any(c.isspace() for c in value):
                out.append('/' + value.strip('/'))
        return out

    def bulk(self, node, hints) -> list[str]:
        """'/<name>' for each `{ name, data }` of a list literal of jobs."""
        listed = JsSyntax.unwrap(node)
        if listed is None or listed.type != 'array':
            return []
        out = []
        for item in listed.named_children:
            for file, obj in self._file.values.objects(item):
                name = JsSyntax.prop(obj, self.NAME)
                out += self.names(file, name, hints) if name is not None else []
        return out

    def of_processor(self, node, hints) -> list[str]:
        """The jobs a processor passed to a worker (a function, or a name bound or imported to one) dispatches on."""
        found = self._function(self._file, node, 0)
        return self._dispatched(*found, hints) if found is not None else [self.EVERY]

    def of_class(self, decorator_call, hints) -> list[str]:
        """The jobs the `process` method of the class a decorator call is on dispatches on."""
        decorator = decorator_call.parent
        holder = decorator.parent if decorator is not None and decorator.type == 'decorator' else None
        cls = (
            holder.child_by_field_name('declaration')
            if holder is not None and holder.type == 'export_statement'
            else holder
        )
        body = cls.child_by_field_name('body') if cls is not None and cls.type in Functions.CLASSES else None
        for member in body.named_children if body is not None else ():
            if member.type == 'method_definition' and JsSyntax.text(member.child_by_field_name('name')) == self.PROCESS:
                return self._dispatched(self._file, member, hints)
        return [self.EVERY]

    def _function(self, file, node, depth):
        node = JsSyntax.unwrap(node)
        if node is None or depth > self.MAX_DEPTH:
            return None
        if node.type in Functions.FUNCTIONS:
            return file, node
        if node.type != 'identifier':
            return None
        value = file.module.scopes.lookup(node, JsSyntax.text(node))
        if value is not None:
            return self._function(file, value, depth + 1)
        if node.parent is not None and node.parent.type == 'function_declaration':
            return file, node.parent
        imported = file.imported(node)
        return self._function(*imported, depth + 1) if imported is not None else None

    def _dispatched(self, file, fn, hints):
        """'/<case>' for each case of a `switch (job.name)` (or `switch (name)` on a destructured `{ name }`) in the
        processor; EVERY too when a case is not known, or alone when there is no such switch."""
        subject = self._subject(fn)
        out, unknown = [], False
        for switch in JsSyntax.walk(fn.child_by_field_name('body'), {'switch_statement'}) if subject else ():
            if JsSyntax.text(JsSyntax.unwrap(switch.child_by_field_name('value'))) != subject:
                continue
            for case in self._cases(switch):
                found = self.names(file, case.child_by_field_name('value'), hints)
                out += found
                unknown = unknown or not found
        return list(dict.fromkeys(out + [self.EVERY] * (unknown or not out)))

    @staticmethod
    def _cases(switch):
        """The cases of one switch, not those of a switch nested in a case (that one tells apart something else)."""
        body = switch.child_by_field_name('body')
        return [c for c in body.named_children if c.type == 'switch_case'] if body is not None else []

    def _subject(self, fn):
        """What a switch on the job's name is written as: '<param>.name', or 'name' for a destructured parameter."""
        params = fn.child_by_field_name('parameters')
        first = next((p for p in params.named_children if p.type != 'comment'), None) if params is not None else None
        if first is None and fn.child_by_field_name('parameter') is not None:
            first = fn.child_by_field_name('parameter')  # an arrow function's one parameter without parentheses
        pattern = (
            first.child_by_field_name('pattern') if first is not None and first.type in JsSyntax.PARAMETERS else first
        )
        if pattern is not None and pattern.type == 'identifier':
            return f'{JsSyntax.text(pattern)}.{self.NAME}'
        names = {JsSyntax.text(p) for p in JsSyntax.walk(pattern, {'shorthand_property_identifier_pattern'})}
        return self.NAME if pattern is not None and self.NAME in names else ''
