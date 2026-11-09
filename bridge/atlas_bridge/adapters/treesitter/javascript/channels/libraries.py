"""Which library the names of one file come from: `import WebSocket from 'ws'`, `const { Server } = require('ws')`,
`import * as net from 'node:net'`, and which libraries the file imports at all."""

from ..bindings.binding import ValueBinding
from ..syntax.nodes import JsSyntax
from .table import DEFAULT_EXPORTS, GLOBAL


class LibraryNames:
    """Reads the imports and requires of one file (a JsModule) once."""

    DEFAULT = 'default'  # a default or namespace import: the module itself
    NODE = 'node:'  # `node:net` is `net`
    CHAINS = {'member_expression': 'object'}

    def __init__(self, module):
        self._module = module
        self._imports = None  # {local name: (library, exported name)} of the import statements
        self._used = None  # every module the file imports or requires

    def uses(self, libraries) -> bool:
        """The file imports or requires one of the libraries."""
        return bool(self.specs() & libraries)

    def specs(self):
        """Every module the file imports or requires."""
        if self._used is None:
            self._read()
        return self._used

    def qualified(self, callee):
        """(library, name in the library) a callee stands for: `net.connect` -> ('net', 'connect'),
        `WebSocket.Server` with `import WebSocket from 'ws'` -> ('ws', 'WebSocket.Server'), an unbound `WebSocket` ->
        (GLOBAL, 'WebSocket'); None when the callee's first name is bound to something else."""
        props, head = [], JsSyntax.unwrap(callee)
        while head is not None and head.type == 'member_expression':
            props.insert(0, JsSyntax.text(head.child_by_field_name('property')))
            head = JsSyntax.unwrap(head.child_by_field_name('object'))
        if head is None or head.type != 'identifier':
            return None
        name = JsSyntax.text(head)
        found = self._library_of(head, name)
        if found is None:
            return (GLOBAL, '.'.join([name, *props])) if self._unbound(head, name) else None
        library, exported = found
        base = DEFAULT_EXPORTS.get(library, '') if exported == self.DEFAULT else exported
        return library, '.'.join(p for p in (base, *props) if p)

    def source_of(self, head):
        """(module, exported name or 'default') an identifier is imported or required from, or None."""
        return self._library_of(head, JsSyntax.text(head))

    def _unbound(self, head, name):
        return self._module.scopes.binding(head, name) is None and name not in self._import_table()

    def _library_of(self, head, name):
        imported = self._import_table().get(name)
        if imported is not None:
            return imported
        binding = self._module.scopes.binding(head, name)
        if binding is None:
            return None
        if isinstance(binding, ValueBinding):
            return self._required(binding.initializer)
        declarator = binding.node
        if declarator.type != 'variable_declarator':
            return None
        library = self._spec(JsSyntax.require(declarator.child_by_field_name('value')))
        key = self._key(declarator.child_by_field_name('name'), name)
        return (library, key) if library and key else None

    def _required(self, value):
        """`require('ws')` -> ('ws', default); `require('ws').Server` -> ('ws', 'Server')."""
        value = JsSyntax.unwrap(value)
        library = self._spec(JsSyntax.require(value))
        if library:
            return library, self.DEFAULT
        if value is not None and value.type == 'member_expression':
            library = self._spec(JsSyntax.require(value.child_by_field_name('object')))
            if library:
                return library, JsSyntax.text(value.child_by_field_name('property'))
        return None

    @staticmethod
    def _key(pattern, name):
        """The property `{ Server: WsServer }` or `{ Server }` takes `name` from."""
        if pattern is None or pattern.type != 'object_pattern':
            return None
        for p in pattern.named_children:
            if p.type == 'shorthand_property_identifier_pattern' and JsSyntax.text(p) == name:
                return name
            if p.type == 'pair_pattern' and JsSyntax.text(p.child_by_field_name('value')) == name:
                return JsSyntax.text(p.child_by_field_name('key'))
        return None

    @classmethod
    def _spec(cls, spec):
        if not spec:
            return None
        return spec[len(cls.NODE) :] if spec.startswith(cls.NODE) else spec

    def _import_table(self):
        if self._imports is None:
            self._read()
        return self._imports

    def _read(self):
        self._imports, self._used = {}, set()
        root = self._module.source.root
        for node in root.named_children:
            if node.type == 'import_statement':
                self._import_statement(node)
        for call in JsSyntax.walk(root, {'call_expression'}):
            spec = self._spec(JsSyntax.require(call))
            if spec:
                self._used.add(spec)

    def _import_statement(self, node):
        source = node.child_by_field_name('source')
        library = self._spec(JsSyntax.string(source)) if source is not None else None
        if not library:
            return
        self._used.add(library)
        clause = next((c for c in node.named_children if c.type == 'import_clause'), None)
        for c in clause.named_children if clause is not None else ():
            if c.type == 'identifier':
                self._imports[JsSyntax.text(c)] = (library, self.DEFAULT)
            elif c.type == 'namespace_import' and c.named_children:
                self._imports[JsSyntax.text(c.named_children[0])] = (library, self.DEFAULT)
            elif c.type == 'named_imports':
                for spec in c.named_children:
                    name, alias = spec.child_by_field_name('name'), spec.child_by_field_name('alias')
                    if name is not None:
                        self._imports[JsSyntax.text(alias or name)] = (library, JsSyntax.text(name))
