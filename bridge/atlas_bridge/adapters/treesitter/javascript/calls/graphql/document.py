"""GraphQL document text: its operations, and the root fields each one selects."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Operation:
    """`query Rooms($city: String) { rooms(city: $city) { id } }` -> kind 'query', name 'Rooms', fields ('rooms',)."""

    kind: str
    name: str
    fields: tuple[str, ...]


class GraphqlDocument:
    """Reads the executable definitions of a GraphQL document (the GraphQL spec's grammar, lexically): operations
    and their root selection, with aliases read as the field they stand for. Fragment definitions are skipped, and so
    are fragment spreads at the root. Text that is not a document (a search string, SQL) reads as no operations."""

    # punctuators, names, numbers, strings (block strings first) and comments; anything else is not GraphQL
    TOKEN = re.compile(
        r'"""[\s\S]*?"""|"(?:[^"\\\n]|\\.)*"|#[^\n]*|\.\.\.|[_A-Za-z]\w*|-?\d[\w.+-]*|[!$&():=@\[\]{|}]|\S'
    )
    NAME = re.compile(r'[_A-Za-z]\w*')  # a GraphQL name
    KINDS = frozenset({'query', 'mutation', 'subscription'})
    FRAGMENT = 'fragment'
    SPREAD = '...'
    META = '__'  # introspection fields (__typename, __schema, __type) are the server's own
    OPEN = {'{': '}', '(': ')', '[': ']'}

    def __init__(self, text: str):
        self._tokens = [t for t in self.TOKEN.findall(text or '') if not t.startswith('#') and t != ',']
        self._i = 0

    def operations(self) -> list[Operation]:
        """The operations of the document, or [] when the text is not a GraphQL document."""
        out = []
        while self._i < len(self._tokens):
            found = self._definition()
            if found is None:
                return []
            if found.kind != self.FRAGMENT:
                out.append(found)
        return out if all(op.fields for op in out) else []

    def _peek(self):
        return self._tokens[self._i] if self._i < len(self._tokens) else ''

    def _definition(self):
        head = self._peek()
        if head == '{':
            return Operation('query', '', self._selection())
        if head not in self.KINDS and head != self.FRAGMENT:
            return None
        self._i += 1
        name = self._peek() if self.NAME.fullmatch(self._peek()) else ''
        while self._peek() not in ('{', ''):  # name, variables, type condition, directives
            if not self._skip_one():
                return None
        if self._peek() != '{':
            return None
        if head == self.FRAGMENT:
            self._skip_one()
            return Operation(self.FRAGMENT, name, ())
        return Operation(head, name, self._selection())

    def _skip_one(self):
        """Step over one token, or over a whole bracketed group; False at a closing bracket with no opening one."""
        token = self._peek()
        if token in self.OPEN.values():
            return False
        self._i += 1
        if token in self.OPEN:
            depth = 1
            while self._i < len(self._tokens) and depth:
                t = self._tokens[self._i]
                depth += (t in self.OPEN) - (t in self.OPEN.values())
                self._i += 1
        return True

    def _selection(self):
        """The root fields of the selection set at the cursor (a '{'); () when it is not one."""
        self._i += 1
        fields = []
        while self._peek() not in ('}', ''):
            field = self._field()
            if field is None:
                return ()
            if field and not field.startswith(self.META):
                fields.append(field)
        if self._peek() != '}':
            return ()
        self._i += 1
        return tuple(dict.fromkeys(fields))

    def _field(self):
        """The field at the cursor ('' for a fragment spread), stepping over its arguments, directives and selection;
        None when the cursor is not at a field."""
        token = self._peek()
        if token == self.SPREAD:
            self._i += 1
            name = ''
        elif self.NAME.fullmatch(token):
            self._i += 1
            name = token
            if self._peek() == ':':
                self._i += 1
                name = self._peek() if self.NAME.fullmatch(self._peek()) else ''
                self._i += 1
        else:
            return None
        while self._peek() not in ('}', '') and not self._starts_field():
            if not self._skip_one():
                return None
        return name

    def _starts_field(self):
        """The cursor is at the next field: a name that is not the type condition of a spread or a directive."""
        token, before = self._peek(), self._tokens[self._i - 1]
        return (token == self.SPREAD or self.NAME.fullmatch(token)) and before not in ('@', 'on', self.SPREAD)
