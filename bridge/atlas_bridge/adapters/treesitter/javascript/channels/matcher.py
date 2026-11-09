"""Which entry of the table a call or `new` expression is, and which earlier entry made the object it is called on."""

from dataclasses import dataclass

from ..bindings.binding import ParamBinding, ValueBinding
from ..syntax.members import Members
from ..syntax.nodes import JsSyntax
from .properties import ParameterProperties
from .table import ANY_NAME, CLIENT_METHODS, ENTRIES, Entry, Form


@dataclass(frozen=True)
class Match:
    """A call of a table entry: the node, its entry, the library it was matched through, and (for an entry called on
    an object) the match that made that object."""

    node: object  # the call_expression or new_expression
    entry: Entry
    library: str
    origin: 'Match | None' = None
    name: str = ''  # the method or member name it was called by ('' for a computed one: `stub[method](...)`)


class EntryIndex:
    """ENTRIES by (form, callee), in table order."""

    def __init__(self, entries):
        self._by = {}
        for e in entries:
            self._by.setdefault((e.form, e.callee), []).append(e)

    def get(self, form, callee):
        return self._by.get((form, callee), ())


class Matcher:
    """Matches the calls of one file (a ChannelFile) against ENTRIES."""

    INDEX = EntryIndex(ENTRIES)
    MAX_DEPTH = 5  # bindings and fields followed to the object a method is called on

    def __init__(self, file):
        self._file = file

    def match(self, node) -> Match | None:
        """The entry a call or `new` expression is (the first that fits), or None."""
        if node.type == 'new_expression':
            return self._new(node)
        if node.type == 'call_expression':
            return self._call(node)
        return None

    def _new(self, node):
        ctor = JsSyntax.unwrap(node.child_by_field_name('constructor'))
        found = self._qualified(node, Form.NEW, ctor)
        if found is None and ctor is not None and ctor.type == 'member_expression':
            origin = self.origin(ctor.child_by_field_name('object'))
            name = JsSyntax.text(ctor.child_by_field_name('property'))
            found = self._on(node, Form.ON_NEW, name, origin)
        return found

    def _call(self, node):
        fn = JsSyntax.unwrap(node.child_by_field_name('function'))
        if fn is None:
            return None
        found = self._qualified(node, Form.CALL, fn)
        if found is not None or fn.type not in ('member_expression', 'subscript_expression'):
            return found
        receiver = fn.child_by_field_name('object')
        name = JsSyntax.text(fn.child_by_field_name('property')) if fn.type == 'member_expression' else ''
        found = self._on(node, Form.ON_CALL, name, self.origin(receiver))
        return found or self._method(node, name)

    def _qualified(self, node, form, callee):
        """A constructor or function of a library, by the name it has there."""
        if callee is None or callee.type not in ('identifier', 'member_expression'):
            return None
        q = self._file.libraries.qualified(callee)
        if q is None:
            return None
        library, name = q
        entry = next((e for e in self.INDEX.get(form, name) if library in e.libraries), None)
        return Match(node, entry, library) if entry is not None else None

    def _on(self, node, form, name, origin):
        """A method of an object an earlier entry made (any method, for an entry named ANY_NAME)."""
        if origin is None:
            return None
        for callee in (name, ANY_NAME):
            for entry in self.INDEX.get(form, callee):
                if entry.on == origin.entry.makes and self._named(entry, name):
                    return Match(node, entry, origin.library, origin, name)
        return None

    @staticmethod
    def _named(entry, name):
        return entry.callee != ANY_NAME or name not in CLIENT_METHODS

    def _method(self, node, name):
        """A method called in a file that imports the entry's library."""
        count = len(JsSyntax.args(node))
        for entry in self.INDEX.get(Form.METHOD, name):
            used = entry.libraries & self._file.libraries.specs()
            if used and entry.fits(count):
                return Match(node, entry, min(used), name=name)
        return None

    def origin(self, expr, depth=0) -> Match | None:
        """The match that made the object `expr` stands for: a call that makes one, a const bound to it, a field
        set to it (`this.ws = new WebSocket(url)`), or a member of an object whose members are that object too."""
        expr = JsSyntax.unwrap(expr)
        if expr is None or depth > self.MAX_DEPTH:
            return None
        if expr.type in ('call_expression', 'new_expression'):
            found = self.match(expr)
            return found if found is not None and found.entry.makes else None
        if expr.type == 'identifier':
            return self._bound(expr, depth)
        if expr.type != 'member_expression':
            return None
        obj = JsSyntax.unwrap(expr.child_by_field_name('object'))
        if obj is not None and obj.type == 'this':
            field = JsSyntax.text(expr.child_by_field_name('property'))
            found = next(filter(None, (self.origin(v, depth + 1) for v in Members.of_this(expr, field))), None)
            return found if found is not None else self._injected(expr, field)
        inner = self.origin(obj, depth + 1)
        return inner if inner is not None and inner.entry.nested else None

    def _injected(self, expr, field):
        """A constructor parameter property a decorator injects (`@InjectQueue('mail') private queue: Queue`)."""
        param = ParameterProperties.of(expr, field)
        for call in ParameterProperties.decorators(param) if param is not None else ():
            found = self.match(call)
            if found is not None and found.entry.makes:
                return found
        return None

    def _bound(self, ident, depth):
        binding = self._file.module.scopes.binding(ident, JsSyntax.text(ident))
        if isinstance(binding, ValueBinding):
            return self.origin(binding.initializer, depth + 1)
        if isinstance(binding, ParamBinding) and binding.node.type == 'variable_declarator':
            inner = self.origin(binding.node.child_by_field_name('value'), depth + 1)  # const { pkg } = made()
            return inner if inner is not None and inner.entry.nested else None
        return None
