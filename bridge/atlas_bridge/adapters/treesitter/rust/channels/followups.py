"""Where what a call returns goes next: `UdpSocket::bind(a)` then `recv_from`, `TcpListener::bind(a)` into a server."""

from ..syntax import RustSyntax
from ..values.functions import CrateFunctions


class Followups:
    """The value is followed where it is written to go: chained onto the call, a `let` used in the same fn, or a
    struct field it is stored in (`Self { socket }`) used as `self.socket` in an impl of that struct."""

    # Wrappers between a call and the name it is bound to: `UdpSocket::bind(a)?`, `.await`, `.unwrap()`.
    PASSING = frozenset({'unwrap', 'expect'})
    CLIMB = frozenset({'try_expression', 'await_expression', 'parenthesized_expression'})

    def __init__(self, workspace):
        self._workspace = workspace

    def used(self, file, call, methods) -> bool:
        node = call
        while file.has_outer_call(node):
            node = file.outer_call(node)
            if self._method(node) in methods:
                return True
        name = self._bound_name(call)
        fn = RustSyntax.ancestor(call, ('function_item',))
        if name is None or fn is None:
            return False
        if any(self._root(c) == name for c in self._calls(fn, methods)):
            return True
        fields = self._stored(fn, name)
        return bool(fields) and any(
            self._root(c) == 'self' and self._field(c) in fields.get(CrateFunctions.impl_type(c), ())
            for f in self._workspace.files
            for c in f.nodes('call')
            if self._method(c) in methods
        )

    def handed(self, call, callees) -> bool:
        """Whether what `call` returns is passed to a call named in `callees`: directly (`serve(bind(a)?, ..)`) or
        through the name it is bound to in its fn (`let l = bind(a)?; serve(l, ..)`)."""
        node = self._climb(call)
        if node.parent is not None and node.parent.type == 'arguments':
            return self._callee(node.parent.parent) in callees
        name = self._bound_name(call)
        fn = RustSyntax.ancestor(call, ('function_item',))
        if name is None or fn is None:
            return False
        return any(
            self._callee(c) in callees and any(RustSyntax.text(i) == name for i in self._arguments(c))
            for c in RustSyntax.walk(fn, ('call_expression',))
        )

    def _climb(self, call):
        """The outermost expression that is still the call's value: through `?`, `.await`, `.unwrap()`."""
        node = call
        while True:
            parent = node.parent
            if parent is not None and parent.type in self.CLIMB:
                node = parent
            elif parent is not None and parent.type == 'field_expression' and self._passing(parent):
                node = parent.parent
            else:
                return node

    def _bound_name(self, call):
        """The name `let name = <call>` (through `?`, `.await`, `.unwrap()`) binds, or None."""
        node = self._climb(call)
        let = node.parent
        if let is None or let.type != 'let_declaration' or let.child_by_field_name('value') != node:
            return None
        return RustSyntax.text(let.child_by_field_name('pattern')).replace('mut ', '').strip()

    def _passing(self, field):
        call = field.parent
        named = RustSyntax.text(field.child_by_field_name('field')) in self.PASSING
        return named and call is not None and call.type == 'call_expression'

    @staticmethod
    def _stored(fn, name):
        """{struct name: {field}} of the struct expressions in `fn` that store the variable `name`."""
        out = {}
        for e in RustSyntax.walk(fn, ('struct_expression',)):
            owner = RustSyntax.text(e.child_by_field_name('name')).split('::')[-1]
            owner = CrateFunctions.impl_type(e) if owner == 'Self' else owner
            body = e.child_by_field_name('body')
            for i in body.named_children if body is not None else ():
                if i.type == 'shorthand_field_initializer' and RustSyntax.text(i) == name:
                    out.setdefault(owner, set()).add(name)
                elif i.type == 'field_initializer' and RustSyntax.text(i.child_by_field_name('value')) == name:
                    out.setdefault(owner, set()).add(RustSyntax.text(i.child_by_field_name('field')))
        return out

    def _calls(self, fn, methods):
        return [c for c in RustSyntax.walk(fn, ('call_expression',)) if self._method(c) in methods]

    @staticmethod
    def _method(call):
        fn = RustSyntax.method(call)
        return RustSyntax.text(fn.child_by_field_name('field')) if fn is not None else None

    @staticmethod
    def _callee(call):
        """The name a call calls: `axum::serve(..)` -> 'serve', `server.listen(..)` -> 'listen'."""
        fn = call.child_by_field_name('function') if call is not None else None
        if fn is not None and fn.type == 'field_expression':
            return RustSyntax.text(fn.child_by_field_name('field'))
        return RustSyntax.text(fn).split('::')[-1] if fn is not None and fn.type in RustSyntax.NAMES else None

    @staticmethod
    def _arguments(call):
        """Every identifier in a call's arguments: `serve(TcpListenerStream::new(listener))` has 'listener'."""
        args = call.child_by_field_name('arguments')
        return RustSyntax.identifiers(args) if args is not None else ()

    @staticmethod
    def _root(call):
        """The name a method call's receiver chain starts from: `self.socket.recv_from(..)` -> 'self'."""
        root = RustSyntax.chain_root(RustSyntax.method(call).child_by_field_name('value'))
        return RustSyntax.text(root) if root is not None else ''

    @staticmethod
    def _field(call):
        """The field a method is called on: `self.socket.recv_from(..)` -> 'socket'."""
        value = RustSyntax.unwrap(RustSyntax.method(call).child_by_field_name('value'))
        return RustSyntax.text(value.child_by_field_name('field')) if value.type == 'field_expression' else ''
