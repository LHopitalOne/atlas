"""The channels a matched call names, as paths: read from its arguments the way its table entry says."""

from ...kit import UrlTemplate
from ..syntax.functions import Functions
from ..syntax.nodes import JsSyntax
from ..values.urls import UrlText
from .jobs import JobReadings
from .table import Reading


class ChannelReadings:
    """Reads the channels of the matches of one file (a ChannelFile)."""

    SERVICE = 'service'  # `<pkg>.<Service>.service`: the definition a gRPC server adds
    IMPLEMENTATIONS = frozenset({'pair', 'method_definition', 'shorthand_property_identifier'})
    PORTS = range(1, 65536)  # 0 asks the system for any free port: no channel

    def __init__(self, file):
        self._file = file
        self._values = file.values
        self._jobs = JobReadings(file)

    def of(self, match, hints) -> list[str]:
        """The channel paths of a match, in the order found, without repeats; hints gathers the names read."""
        reader = {
            Reading.URL: self._urls,
            Reading.NAME: self._names,
            Reading.PORT: self._ports,
            Reading.ORIGIN: lambda m, h: self.of(m.origin, h),
            Reading.SERVICE: self._service,
            Reading.RPC: self._rpcs,
            Reading.IMPLEMENTATION: self._implementations,
            Reading.JOB: lambda m, h: self._queued(self.of(m.origin, h), self._names(m, h)),
            Reading.JOBS: lambda m, h: self._queued(self.of(m.origin, h), self._jobs.bulk(self._first(m), h)),
            Reading.WORKER: lambda m, h: self._queued(self._names(m, h), self._jobs.of_processor(self._second(m), h)),
            Reading.PROCESSOR: lambda m, h: self._queued(self._names(m, h), self._jobs.of_class(m.node, h)),
        }.get(match.entry.reading)
        return list(dict.fromkeys(reader(match, hints))) if reader is not None else []

    @staticmethod
    def _queued(queues, jobs):
        """'/<queue>/<job>' for each queue and job (both read as '/<name>')."""
        return [q + j for q in queues for j in jobs]

    @staticmethod
    def _first(match):
        args = JsSyntax.args(match.node)
        return args[0] if args else None

    @staticmethod
    def _second(match):
        args = JsSyntax.args(match.node)
        return args[1] if len(args) > 1 else None

    def _urls(self, match, hints):
        for value in self._raw(match, hints):
            if UrlText.path_like(value):
                url = UrlTemplate.split(UrlText.with_params(value))
                hints.update(url.hints)
                if url.path is not None:
                    yield url.path

    def _names(self, match, hints):
        for value in self._raw(match, hints):
            if value and not UrlText.PLACEHOLDER.search(value) and not any(c.isspace() for c in value):
                yield '/' + value.strip('/')

    def _ports(self, match, hints):
        for value in self._raw(match, hints):
            value = value.strip()
            if value.isdigit() and int(value) in self.PORTS:
                yield f'/{int(value)}'

    def _raw(self, match, hints):
        """The literal values the entry's argument holds (one per caller when it is a parameter)."""
        arg, args = match.entry.arg, JsSyntax.args(match.node)
        if arg.after:
            return [v for n in self._after(arg.after, args) for v in self._values.candidates(n, hints)]
        index = self._index(arg, args)
        if index >= len(args):
            return [arg.default] if arg.default else []
        hints.update(JsSyntax.names_in(args[index]))
        objects = self._values.objects(args[index])
        if objects:
            return self._options(arg, objects[0], hints)
        if not arg.positional:
            return []
        nodes = args[index:] if arg.every else args[index : index + 1]
        return [v for n in nodes for v in self._values.candidates(n, hints)]

    @staticmethod
    def _after(token, args):
        """The first half of the arguments after the literal `token` (any case): the keys before their ids."""
        at = next((i for i, a in enumerate(args) if (JsSyntax.string(JsSyntax.unwrap(a)) or '').upper() == token), -1)
        rest = args[at + 1 :] if at >= 0 else []
        return rest[: len(rest) // 2]

    @staticmethod
    def _index(arg, args):
        """The argument's position: `long_index` when the call has an argument there that is not a callback."""
        long = arg.long_index
        if 0 <= long < len(args) and JsSyntax.unwrap(args[long]).type not in Functions.FUNCTIONS:
            return long
        return arg.index

    @staticmethod
    def _options(arg, found, hints):
        """The channels of an options object: its `key`, the list under `many`, or the default."""
        file, options = found
        if arg.unless and JsSyntax.prop(options, arg.unless) is not None:
            return []
        node = JsSyntax.prop(options, arg.key) if arg.key else None
        if node is not None:
            return file.values.candidates(node, hints)
        listed = JsSyntax.unwrap(JsSyntax.prop(options, arg.many)) if arg.many else None
        if listed is not None and listed.type == 'array':
            return [v for n in listed.named_children for v in file.values.candidates(n, hints)]
        return [arg.default] if arg.default else []

    def _service(self, match, hints):
        """`new <pkg>.<Service>(address, credentials)`: '/<Service>'."""
        ctor = JsSyntax.unwrap(match.node.child_by_field_name('constructor'))
        hints.update(JsSyntax.names_in(match.node))
        yield '/' + JsSyntax.text(ctor.child_by_field_name('property'))

    def _rpcs(self, match, hints):
        """`client.<Method>(...)`, or `client[method](...)` with the method's name in a value: '/<Service>/<Method>'."""
        names = [match.name] if match.name else self._computed(match.node, hints)
        for service in self.of(match.origin, hints):
            for name in names:
                yield f'{service}/{name}'

    def _computed(self, node, hints):
        fn = JsSyntax.unwrap(node.child_by_field_name('function'))
        index = fn.child_by_field_name('index') if fn is not None and fn.type == 'subscript_expression' else None
        found = self._values.candidates(index, hints) if index is not None else []
        return [v for v in found if v.isidentifier()]

    def _implementations(self, match, hints):
        """`server.addService(<pkg>.<Service>.service, { <Method>: impl, ... })`: '/<Service>/<Method>' for each."""
        args = JsSyntax.args(match.node)
        definition = JsSyntax.unwrap(args[0]) if len(args) > 1 else None
        if definition is None or definition.type != 'member_expression':
            return
        if JsSyntax.text(definition.child_by_field_name('property')) != self.SERVICE:
            return
        service = JsSyntax.last_name(definition.child_by_field_name('object'))
        objects = self._values.objects(args[1])
        if not service or not objects:
            return
        hints.update(JsSyntax.names_in(definition))
        for member in objects[0][1].named_children:
            if member.type in self.IMPLEMENTATIONS:
                key = member.child_by_field_name('key') or member.child_by_field_name('name') or member
                yield f'/{service}/{JsSyntax.text(key)}'
