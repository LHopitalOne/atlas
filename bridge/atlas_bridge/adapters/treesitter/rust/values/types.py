"""The type an expression holds, as far as declarations say: annotations, constructors, struct fields."""

from ..names import ItemPath
from ..syntax import RustSyntax
from .functions import CrateFunctions


class ValueTypes:
    """of(file, expr) -> the full path of the type an expression holds ('std::net::UdpSocket', 'Config'), or None.

    Read from what is written, never guessed from names: a `let` annotation or value, a parameter's type, `self`
    in an impl, a struct field's declared type, a struct expression, a crate fn's declared return type, a library
    constructor called on a type (`UdpSocket::bind(..)`), and what a library call returns by the table it is given
    (`client.get_multiplexed_async_connection()` is a `redis::aio::MultiplexedConnection`)."""

    # Types that hand out the value they hold: `Arc<UdpSocket>` calls UdpSocket's methods; `io::Result<Self>`.
    HOLDERS = frozenset({'Arc', 'Rc', 'Box', 'Result', 'Option'})
    # Calls on a value that yield the value itself (or what it holds).
    PASSING = frozenset({'unwrap', 'expect', 'clone', 'as_ref'})
    # Associated fns that by convention return their own type (std, tokio and async-std sockets do).
    CONSTRUCTORS = frozenset({'new', 'bind', 'connect', 'connect_timeout', 'from_std'})
    MAX_HOPS = 8

    def __init__(self, workspace, functions, structs, returns=None):
        self._workspace = workspace
        self._functions = functions
        self._structs = structs
        self._returns = returns or {}  # (type path, fn or method) -> the type path a library call returns

    def of(self, file, node, hops=0):
        node = RustSyntax.unwrap(node)
        if node is None or hops > self.MAX_HOPS:
            return None
        t = node.type
        if t == 'self':
            return CrateFunctions.impl_type(node) or None
        if t == 'identifier':
            return self._named(file, node, hops)
        if t == 'field_expression':
            return self._field(file, node, hops)
        if t == 'struct_expression':
            return self._declared(file, node.child_by_field_name('name'), node)
        if t == 'call_expression':
            return self._call(file, node, hops)
        return None

    def _named(self, file, node, hops):
        value = self._workspace.binding(file, node)
        if value is not None:
            let = value.parent
            annotation = let.child_by_field_name('type') if let.type == 'let_declaration' else None
            if annotation is not None:
                return self._declared(file, annotation, let)
            return self.of(file, value, hops + 1)
        fn = RustSyntax.ancestor(node, ('function_item',))
        params = fn.child_by_field_name('parameters') if fn is not None else None
        for p in params.named_children if params is not None else ():
            if p.type == 'parameter' and RustSyntax.text(p.child_by_field_name('pattern')) == RustSyntax.text(node):
                return self._declared(file, p.child_by_field_name('type'), p)
        return None

    def _field(self, file, node, hops):
        owner = self.of(file, node.child_by_field_name('value'), hops + 1)
        if owner is None:
            return None
        found = self._structs.field_type(owner.split('::')[-1], RustSyntax.text(node.child_by_field_name('field')))
        return self._declared(found[0], found[1], found[1]) if found is not None else None

    def _call(self, file, node, hops):
        fn = RustSyntax.method(node)
        if fn is not None:
            name = RustSyntax.text(fn.child_by_field_name('field'))
            owner = self.of(file, fn.child_by_field_name('value'), hops + 1)
            return owner if name in self.PASSING else self._returns.get((owner, name))
        target = self._functions.target(file, node)
        if target is not None:
            returns = target[1].child_by_field_name('return_type')
            return self._declared(target[0], returns, target[1]) if returns is not None else None
        segs = ItemPath.imported(file, node.child_by_field_name('function'))
        returned = self._returns.get(('::'.join(segs[:-1]), segs[-1])) if len(segs) > 1 else None
        if returned is not None:
            return returned
        if len(segs) > 1 and segs[-1] in self.CONSTRUCTORS and segs[-2][:1].isupper():
            return '::'.join(segs[:-1])
        return None

    def _declared(self, file, type_node, at):
        """The full path a written type names, seen through references and HOLDERS; `Self` is the impl's type."""
        node = type_node
        while node is not None and node.type in ('reference_type', 'generic_type'):
            if node.type == 'reference_type':
                node = node.child_by_field_name('type')
            elif ItemPath.last(node.child_by_field_name('type')) in self.HOLDERS:
                args = node.child_by_field_name('type_arguments')
                node = args.named_children[0] if args is not None and args.named_children else None
            else:
                node = node.child_by_field_name('type')
        if node is None:
            return None
        segs = ItemPath.imported(file, node)
        if segs == ['Self']:
            return CrateFunctions.impl_type(at) or None
        return '::'.join(segs) if segs else None
