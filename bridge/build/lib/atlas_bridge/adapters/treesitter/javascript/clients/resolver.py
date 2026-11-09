"""Which client a receiver is, as a ClientSpec: from its binding, its type, its import or its options."""

from ...kit import UrlTemplate
from ..bindings.imports import ImportTable
from ..bindings.scopes import Scopes
from ..syntax.members import Members
from ..syntax.nodes import JsSyntax
from ..values.resolver import UrlValues
from .registry import ClientRegistry
from .specs import ClientClass, ClientFactory, ClientVariable, KnownBase


class ClientResolver:
    """Reads the clients of one file."""

    MAX_DEPTH = 5  # bindings followed to where a client is made
    MADE = frozenset({'new_expression', 'call_expression'})

    def __init__(self, source, scopes: Scopes, imports: ImportTable, values: UrlValues):
        self._source = source
        self._scopes = scopes
        self._imports = imports
        self._values = values
        self._types = None

    def client(self, obj, hints):
        """The spec of the client `obj` is, or None when nothing says where it comes from."""
        obj = JsSyntax.unwrap(obj)
        if obj.type == 'identifier':
            return self._named(obj, hints)
        if obj.type == 'member_expression':  # this.api, this.props.api, props.api
            return self._member(obj, hints)
        if obj.type in self.MADE:
            return self.made_by(obj, hints)
        return None

    def made_by(self, value, hints):
        """The spec of an expression that makes or names a client."""
        return self._made_by(value, hints, 0)

    def base_option(self, options, hints):
        """The path of the base URL in a client's options object (`{baseURL: 'http://orders/api'}` -> '/api')."""
        for key in ClientRegistry.BASE_KEYS:
            node = JsSyntax.prop(options, key)
            if node is not None:
                url = UrlTemplate.split(self._values.resolve(node, hints) or '')
                hints.update(url.hints)
                return url.path or ''
        return None

    def _named(self, obj, hints):
        name = JsSyntax.text(obj)
        binding = self._scopes.binding(obj, name)
        if binding is None:
            return self._imported(name)
        if binding.initializer is not None:
            return self.made_by(binding.initializer, hints)
        return ClientClass.typed(binding.annotated_type(name) or self._member_types().get(name))

    def _member(self, obj, hints):
        field = JsSyntax.text(obj.child_by_field_name('property'))
        if JsSyntax.unwrap(obj.child_by_field_name('object')).type == 'this':
            for value in Members.of_this(obj, field):
                spec = self.made_by(value, hints)
                if spec is not None:
                    return spec
        return ClientClass.typed(self._member_types().get(field))

    def _imported(self, name):
        exported = self._imports.exported_name(name)
        return ClientVariable(exported) if exported is not None else None

    def _made_by(self, value, hints, depth):
        value = JsSyntax.unwrap(value)
        if value is None or depth >= self.MAX_DEPTH:
            return None
        if value.type in self.MADE:
            return self._construction(value, hints)
        if value.type == 'identifier':
            name = JsSyntax.text(value)
            bound = self._scopes.lookup(value, name)
            if bound is not None:
                return self._made_by(bound, hints, depth + 1)
            return self._imported(name)
        return None

    def _construction(self, value, hints):
        """`new Client({baseUrl})`, `axios.create({baseURL})`, `makeClient()`."""
        args = JsSyntax.args(value)
        base = self.base_option(args[0], hints) if args else None
        if base is not None:
            return KnownBase(base)
        made = value.type == 'new_expression'
        callee = value.child_by_field_name('constructor' if made else 'function')
        if callee is not None and callee.type == 'identifier':
            return (ClientClass if made else ClientFactory)(JsSyntax.text(callee))
        return None

    def _member_types(self):
        if self._types is None:
            self._types = Members.declared_types(self._source.root)
        return self._types
